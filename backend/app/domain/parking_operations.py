"""Operación del parqueadero: tarifas, entrada, cotización, cobro y caja.

docs/05 §3: porta parking_operations.py con las reglas verificadas —
transacción BEGIN IMMEDIATE para cobro + cierre + recibo juntos,
idempotencia de cobro, sólo CASH registra efectivo y cambio, y el
cobro en efectivo exige turno abierto.
"""
from __future__ import annotations

import re
import secrets
import uuid
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from datetime import UTC, datetime

from ..config import BILLING_SCHEMES
from ..db import execute, query, query_one, transaction
from . import authentication as auth
from . import time_utils
from .errors import (
    AuthorizationError, ConflictError, DomainError, IdempotencyConflictError,
    NotFoundError,
)

D0 = Decimal("0")
ACTIVE_STATUSES = ("ACTIVE", "PENDING_PAYMENT", "PAID", "CANCELLED")
_Plate_NORM = re.compile(r"[^A-Z0-9]")


# ── Normalización ─────────────────────────────────────────────────────

def normalise_plate(raw: str) -> str:
    """Mayúsculas sin espacios; 3–15 alfanuméricos (docs/05 §3)."""
    plate = _Plate_NORM.sub("", (raw or "").upper())
    if not (3 <= len(plate) <= 15) or not plate.isalnum():
        raise DomainError("La placa debe tener 3 a 15 caracteres alfanuméricos.")
    return plate


# ── Tarifas ───────────────────────────────────────────────────────────

def configure_tariff(site_id: int, vehicle_type_id: int, name: str, scheme: str,
                     amount: Decimal | str, grace_minutes: int = 0,
                     fraction_minutes: int | None = None, actor: dict | None = None) -> None:
    """Crea un plan versionado: una tarifa anterior no se edita (docs/05 §8)."""
    if scheme not in BILLING_SCHEMES:
        raise DomainError(f"Esquema de cobro inválido. Use uno de: {', '.join(BILLING_SCHEMES)}")
    amount_d = Decimal(str(amount))
    if amount_d < 0:
        raise DomainError("El monto no puede ser negativo.")
    now = time_utils.iso_utc()
    with transaction() as conn:
        # desactiva el plan vigente anterior para este tipo (versionado)
        conn.execute(
            "UPDATE tariff_plans SET valid_until = ? "
            "WHERE site_id = ? AND vehicle_type_id = ? AND valid_until IS NULL AND is_active = 1",
            (now, site_id, vehicle_type_id))
        conn.execute(
            "INSERT INTO tariff_plans (site_id, vehicle_type_id, name, billing_scheme, "
            "valid_from, valid_until, is_active, created_by_user_id) VALUES (?,?,?,?,?,?,1,?)",
            (site_id, vehicle_type_id, name, scheme, now, None, actor["id"] if actor else None))
        plan_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            "INSERT INTO tariff_rules (tariff_plan_id, sequence_no, start_minute, end_minute, "
            "amount, grace_minutes, fraction_minutes) VALUES (?, 1, 0, NULL, ?, ?, ?)",
            (plan_id, amount_d, grace_minutes, fraction_minutes))
        auth._audit(conn, actor["id"] if actor else None, "tariff_plan", plan_id,
                    "TARIFF_CREATED", None,
                    {"nombre": name, "esquema": scheme, "monto": str(amount_d)})


def active_tariffs(site_id: int) -> list[dict]:
    """Tarifas vigentes con alias en español para la UI (fix UX-D-CONTRATO):
    el monto/gracia corresponden a la última regla del plan (mayor start_minute,
    y a igualdad la mayor sequence_no)."""
    return query(
        "SELECT p.*, p.name AS nombre, p.billing_scheme AS esquema, "
        "t.code AS tipo_vehiculo, t.name AS tipo_nombre, "
        "(SELECT r.amount FROM tariff_rules r WHERE r.tariff_plan_id = p.id "
        " ORDER BY r.start_minute DESC, r.sequence_no DESC LIMIT 1) AS monto, "
        "(SELECT r.grace_minutes FROM tariff_rules r WHERE r.tariff_plan_id = p.id "
        " ORDER BY r.start_minute DESC, r.sequence_no DESC LIMIT 1) AS gracia_minutos "
        "FROM tariff_plans p JOIN vehicle_types t ON t.id = p.vehicle_type_id "
        "WHERE p.site_id = ? AND p.is_active = 1 ORDER BY t.code, p.valid_from DESC",
        (site_id,))


def _tariff_for(site: dict, vehicle_type_id: int, at: datetime) -> dict | None:
    return query_one(
        "SELECT p.*, r.amount AS rule_amount, r.grace_minutes, r.fraction_minutes "
        "FROM tariff_plans p LEFT JOIN tariff_rules r ON r.tariff_plan_id = p.id "
        "WHERE p.site_id = ? AND p.vehicle_type_id = ? AND p.is_active = 1 "
        "AND p.valid_from <= ? AND (p.valid_until IS NULL OR p.valid_until >= ?) "
        "ORDER BY p.valid_from DESC LIMIT 1",
        (site["id"], vehicle_type_id, time_utils.iso_utc(at), time_utils.iso_utc(at)))


def calculate_tariff(plan: dict, minutes: int) -> Decimal:
    """Los 7 esquemas de cobro (docs/05 §3).

    Cada regla tiene grace_minutes y fraction_minutes; los minutos dentro
    de la gracia no se cobran.
    """
    grace = int(plan.get("grace_minutes") or 0)
    amount = Decimal(str(plan.get("rule_amount") or plan.get("amount") or 0))
    fraction = int(plan.get("fraction_minutes") or 0)
    billable = max(0, int(minutes) - grace)
    if billable <= 0:
        return D0
    scheme = plan["billing_scheme"]

    def units(size: int) -> int:
        return -(-billable // size)  # ceil división

    if scheme == "MINUTE":
        return amount * Decimal(billable)
    if scheme == "HOUR":
        return amount * Decimal(units(60))
    if scheme == "HOUR_FRACTION":
        frac = fraction or 30
        return amount * Decimal(units(frac))
    if scheme == "FLAT_ENTRY":
        return amount
    if scheme == "BLOCKS":
        block = fraction or 60
        return amount * Decimal(units(block))
    if scheme == "DAY":
        return amount * Decimal(units(1440))
    if scheme == "NIGHT":
        # tarifa nocturna: cada noche iniciada (24 h começadas) cobra el monto
        return amount * Decimal(units(fraction or 1440))
    raise DomainError(f"Esquema desconocido: {scheme}")


def money(d: Decimal) -> str:
    """Importes como cadena decimal — nunca float (docs/04 §4.1)."""
    return str(Decimal(d).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ── Estadías ──────────────────────────────────────────────────────────

def _tid(user: dict) -> int:
    """El tenant SIEMPRE sale de la sesión; nunca del body ni de la URL."""
    tid = (user or {}).get("tenant_id")
    if not tid:
        raise AuthorizationError("La petición requiere una sesión de tenant.")
    return int(tid)


def site(tenant: dict | int | None = None) -> dict:
    """Sede operativa del tenant: su primera sede activa (decisión del plan
    multi-tenant; la selección por usuario viene después)."""
    tid = tenant["id"] if isinstance(tenant, dict) else tenant
    if tid is None:
        raise AuthorizationError("La petición requiere una sesión de tenant.")
    s = query_one(
        "SELECT * FROM parking_sites WHERE tenant_id = ? AND is_active = 1 ORDER BY id LIMIT 1",
        (tid,))
    if not s:
        raise NotFoundError("No existe la sede activa.")
    return s


def find_vehicle(plate: str, tenant_id: int | None = None) -> dict | None:
    """Placa única por TENANT (UNIQUE(tenant_id, plate)); el filtro es
    obligatorio para no cruzar tenants con la misma placa."""
    if tenant_id is None:
        raise AuthorizationError("La búsqueda de vehículo exige el tenant de la sesión.")
    return query_one(
        "SELECT * FROM vehicles WHERE plate = ? AND tenant_id = ?", (plate, tenant_id))


def find_vehicle_by_id(vehicle_id: int) -> dict | None:
    return query_one("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))


def find_active_stay(plate: str, tenant_id: int | None = None) -> dict | None:
    v = find_vehicle(plate, tenant_id)
    if not v:
        return None
    return query_one(
        "SELECT s.* FROM parking_stays s WHERE s.vehicle_id = ? AND s.status IN ('ACTIVE','PENDING_PAYMENT') "
        "ORDER BY s.entry_at DESC LIMIT 1", (v["id"],))


def _find_valid_subscription(vehicle_id: int, site: dict, at: datetime) -> dict | None:
    today = time_utils.today_for_site(site)
    sub = query_one(
        "SELECT sub.* FROM subscriptions sub "
        "JOIN subscription_vehicles sv ON sv.subscription_id = sub.id "
        "WHERE sv.vehicle_id = ? AND sub.site_id = ? AND sub.status = 'ACTIVE' "
        "AND sub.starts_on <= ? AND sub.expires_on >= ? "
        "ORDER BY sub.expires_on DESC LIMIT 1",
        (vehicle_id, site["id"], today.isoformat(), today.isoformat()))
    if not sub:
        return None
    if sub["permitted_start"] and sub["permitted_end"]:
        local_now = at.astimezone(time_utils.site_tz(site)).strftime("%H:%M")
        if not _hora_en_ventana(local_now, sub["permitted_start"], sub["permitted_end"]):
            return None
    return sub


def _hora_en_ventana(hhmm: str, desde: str, hasta: str) -> bool:
    """Ventana que puede cruzar medianoche (docs/11 §11.2)."""
    if desde == hasta:
        return True
    if desde < hasta:
        return desde <= hhmm <= hasta
    return hhmm >= desde or hhmm <= hasta  # cruza medianoche


def register_entry(user: dict, plate_raw: str, vehicle_type: str = "CAR") -> dict:
    site_row = site(user["tenant_id"])
    tid = _tid(user)
    plate = normalise_plate(plate_raw)
    if find_active_stay(plate, tid):
        raise ConflictError(f"La placa {plate} ya tiene una estadía activa.")

    type_row = query_one("SELECT * FROM vehicle_types WHERE code = ?", (vehicle_type,))
    if not type_row:
        raise DomainError("Tipo de vehículo inválido.")

    # la fecha del sitio se resuelve ANTES de la transacción (docs/05 §6)
    now = time_utils.utcnow()
    with transaction() as conn:
        vehicle = conn.execute(
            "SELECT * FROM vehicles WHERE plate = ? AND tenant_id = ?", (plate, tid)).fetchone()
        if vehicle:
            vehicle_id = dict(vehicle)["id"]
        else:
            conn.execute(
                "INSERT INTO vehicles (tenant_id, plate, vehicle_type_id) VALUES (?,?,?)",
                (tid, plate, type_row["id"]))
            vehicle_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.execute(
            "INSERT INTO parking_stays (site_id, tenant_id, vehicle_id, entry_at, entry_user_id, status) "
            "VALUES (?,?,?,?,?, 'ACTIVE')",
            (site_row["id"], tid, vehicle_id, time_utils.iso_utc(now), user["id"]))
        stay_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # factura de ingreso en la misma transacción (docs/04 §4.3)
        receipt = _issue_receipt_txn(conn, site_row, receipt_type="ENTRY", stay_id=stay_id,
                                     issued_by=user["id"])
        auth._audit(conn, user["id"], "parking_stay", stay_id, "ENTRY_REGISTERED", None,
                    {"placa": plate, "tipo": vehicle_type})
    return {
        "estadia_id": stay_id,
        "placa": plate,
        "ingreso": time_utils.iso_utc(now),
        "ingreso_local": time_utils.local_str(now, site_row),
        "recibo": receipt,
    }


def quote_exit(user: dict, plate: str) -> dict:
    """Cotizar salida: NO cierra la estadía (docs/04 §4.3)."""
    plate_n = normalise_plate(plate)
    site_row = site(user["tenant_id"])
    stay = find_active_stay(plate_n, user["tenant_id"])
    if not stay:
        raise NotFoundError(f"No hay estadía activa para la placa {plate_n}.")
    vehicle = query_one("SELECT * FROM vehicles WHERE id = ?", (stay["vehicle_id"],))
    minutes = time_utils.elapsed_minutes(stay["entry_at"])
    exit_at = time_utils.utcnow()

    sub = _find_valid_subscription(vehicle["id"], site_row, exit_at)
    if sub:
        monto, esquema, plan_id, descuento = D0, "SUBSCRIPTION", None, D0
    else:
        plan = _tariff_for(site_row, vehicle["vehicle_type_id"], exit_at)
        if not plan:
            raise DomainError("No hay tarifa vigente para este tipo de vehículo.")
        monto = calculate_tariff(plan, minutes)
        esquema, plan_id, descuento = plan["billing_scheme"], plan["id"], D0
    return {
        "estadia_id": stay["id"], "placa": plate_n,
        "entrada_local": time_utils.local_str(time_utils.parse_iso(stay["entry_at"]), site_row),
        "salida_local": time_utils.local_str(exit_at, site_row),
        "minutos": minutes, "esquema": esquema,
        "monto": money(monto), "descuento": money(descuento), "monto_a_cobrar": money(monto),
        "monto_recibido": None, "cambio": None, "tariff_plan_id": plan_id,
        "mensualidad_vigente": sub is not None,
    }


def collect_payment(user: dict, plate, metodo: str, monto: str,
                    efectivo_recibido: str | None = None, referencia: str | None = None,
                    idempotency_key: str | None = None) -> dict:
    """Cobro transaccional (docs/04 §4.13, pasos 1-11)."""
    from . import cash as cash_service

    plate_n = normalise_plate(plate)
    site_row = site(user["tenant_id"])
    tid = _tid(user)
    metodo_up = (metodo or "").upper()
    method_row = query_one("SELECT * FROM payment_methods WHERE code = ?", (metodo_up,))
    if not method_row:
        raise DomainError("Forma de pago inválida.")

    # idempotencia (docs/09 §9.6): la misma clave devuelve el pago existente
    if idempotency_key:
        prev = query_one(
            "SELECT * FROM payments WHERE idempotency_key = ? AND tenant_id = ?",
            (idempotency_key, tid))
        if prev:
            if prev["status"] == "VOIDED":
                raise IdempotencyConflictError()
            stay = query_one("SELECT * FROM parking_stays WHERE id = ?", (prev["stay_id"],))
            veh = query_one("SELECT * FROM vehicles WHERE id = ?", (stay["vehicle_id"],)) if stay else None
            if not veh or (prev["stay_id"] and veh["plate"] != plate_n):
                raise IdempotencyConflictError()
            receipt = query_one(
                "SELECT id, receipt_number, receipt_type AS tipo FROM receipts WHERE payment_id = ?",
                (prev["id"],))
            return {
                "pago_id": prev["id"], "estadia_id": prev["stay_id"], "estado": "PAID",
                "monto": money(Decimal(prev["amount"])),
                "efectivo_recibido": money(Decimal(prev["amount_received"])) if prev["amount_received"] else None,
                "cambio": money(Decimal(prev["change_amount"])) if prev["change_amount"] else None,
                "recibo": receipt, "idempotente": True,
            }

    amount = Decimal(str(monto)) if monto else D0
    received: Decimal | None = None
    change: Decimal | None = None

    # la fecha/hora se resuelve antes de abrir la transacción (docs/05 §6)
    lautc = time_utils.utcnow()
    with transaction() as conn:
        stay = conn.execute(
            "SELECT * FROM parking_stays WHERE vehicle_id IN "
            "(SELECT id FROM vehicles WHERE plate = ? AND tenant_id = ?) "
            "AND tenant_id = ? AND status IN ('ACTIVE','PENDING_PAYMENT') "
            "ORDER BY entry_at DESC LIMIT 1",
            (plate_n, tid, tid)).fetchone()
        if not stay:
            raise NotFoundError(f"No hay estadía activa para la placa {plate_n}.")
        stay = dict(stay)
        vehicle = conn.execute("SELECT * FROM vehicles WHERE id = ?", (stay["vehicle_id"],)).fetchone()
        vehicle = dict(vehicle)

        minutes = time_utils.elapsed_minutes(stay["entry_at"], lautc)
        sub = conn.execute(
            "SELECT sub.* FROM subscriptions sub JOIN subscription_vehicles sv ON sv.subscription_id = sub.id "
            "WHERE sv.vehicle_id = ? AND sub.site_id = ? AND sub.status = 'ACTIVE' "
            "AND sub.starts_on <= date('now') AND sub.expires_on >= date('now') "
            "ORDER BY sub.expires_on DESC LIMIT 1", (vehicle["id"], site_row["id"])).fetchone()
        sub = dict(sub) if sub else None
        if sub and sub["permitted_start"] and sub["permitted_end"] and not _hora_en_ventana(
                lautc.astimezone(time_utils.site_tz(site_row)).strftime("%H:%M"),
                sub["permitted_start"], sub["permitted_end"]):
            sub = None
        plan_id = None  # la estadía guarda la tarifa aplicada (reporte «Por tarifa», docs/04 §4.9)
        if sub:
            monto_final, esquema = D0, "SUBSCRIPTION"
        else:
            plan_row = _tariff_for(site_row, vehicle["vehicle_type_id"], lautc)
            if not plan_row:
                raise DomainError("No hay tarifa vigente para este tipo de vehículo.")
            monto_final = calculate_tariff(plan_row, minutes)
            esquema, plan_id = plan_row["billing_scheme"], plan_row["id"]
        if monto_final >= 0 and amount and amount < monto_final:
            raise DomainError(
                f"El monto indicado ({money(amount)}) es menor al importe calculado ({money(monto_final)}).")
        monto_cobro = monto_final if amount is None or not amount else min(amount, max(amount, monto_final))
        # regla: monto >= cotización; si menor, 400 (docs/04 §4.3)
        monto_cobro = amount if amount else monto_final

        # validación de forma de pago (docs/11 §11.1)
        if metodo_up == "CASH":
            shift = conn.execute(
                "SELECT * FROM cash_shifts WHERE user_id = ? AND site_id = ? AND status = 'OPEN' "
                "ORDER BY opened_at DESC LIMIT 1", (user["id"], site_row["id"])).fetchone()
            if not shift:
                raise DomainError("Cobro en efectivo rechazado: no hay un turno de caja abierto.")
            if efectivo_recibido is None:
                raise DomainError("El cobro en efectivo exige registrar el efectivo recibido.")
            received = Decimal(str(efectivo_recibido))
            if received < monto_cobro:
                raise DomainError(f"Faltan ${money(monto_cobro - received)}")
            change = received - monto_cobro
        else:
            if efectivo_recibido is not None and Decimal(str(efectivo_recibido)) != monto_cobro:
                raise DomainError("Sólo CASH registra efectivo recibido y cambio.")

        paid_at = time_utils.iso_utc(lautc)
        cur = conn.execute(
            "INSERT INTO payments (tenant_id, stay_id, cash_shift_id, payment_method_id, received_by_user_id, "
            "amount, amount_received, change_amount, paid_at, external_reference, idempotency_key, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?, 'APPROVED')",
            (tid, stay["id"],
             (conn.execute("SELECT id FROM cash_shifts WHERE user_id = ? AND site_id = ? AND status = 'OPEN' "
                           "ORDER BY opened_at DESC LIMIT 1",
                           (user["id"], site_row["id"])).fetchone() or {"id": None})["id"]
             if metodo_up == "CASH" else None,
             method_row["id"], user["id"], monto_cobro, received, change, paid_at,
             referencia, idempotency_key if idempotency_key else None))
        pago_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        # cierre de la estadía y del cobro, JUNTOS (docs/04 §4.13)
        conn.execute(
            "UPDATE parking_stays SET exit_at = ?, exit_user_id = ?, status = 'PAID', calculated_amount = ?, "
            "tariff_plan_id = COALESCE(tariff_plan_id, ?) WHERE id = ?",
            (paid_at, user["id"], monto_cobro, plan_id, stay["id"]))
        receipt = _issue_receipt_txn(conn, site_row, receipt_type="EXIT", stay_id=stay["id"],
                                     payment_id=pago_id, issued_by=user["id"])
        auth._audit(conn, user["id"], "payment", pago_id, "PAYMENT_COLLECTED", None,
                    {"placa": plate_n, "monto": money(monto_cobro), "metodo": metodo_up,
                     "cambio": money(change) if change is not None else None})
    return {
        "pago_id": pago_id, "estadia_id": stay["id"], "estado": "PAID",
        "minutos": minutes, "esquema": esquema,
        "monto": money(monto_cobro),
        "efectivo_recibido": money(received) if received is not None else None,
        "cambio": money(change) if change is not None else None,
        "recibo": receipt,
    }


def void_payment(user: dict, payment_id: int, motivo: str) -> dict:
    """Anular cobro: sólo administradores; devuelve la estadía a ACTIVE."""
    auth.require_admin(user)
    tid = _tid(user)
    pago = query_one("SELECT * FROM payments WHERE id = ? AND tenant_id = ?", (payment_id, tid))
    if not pago:
        raise NotFoundError()
    if pago["status"] != "APPROVED":
        raise DomainError("Sólo se anula un pago aprobado.")
    with transaction() as conn:
        conn.execute(
            "UPDATE payments SET status = 'VOIDED', voided_by_user_id = ?, voided_at = ?, void_reason = ? "
            "WHERE id = ?", (user["id"], time_utils.iso_utc(), motivo, payment_id))
        if pago["stay_id"]:
            conn.execute(
                "UPDATE parking_stays SET status = 'ACTIVE', exit_at = NULL, exit_user_id = NULL WHERE id = ?",
                (pago["stay_id"],))
        auth._audit(conn, user["id"], "payment", payment_id, "PAYMENT_VOIDED", None,
                    {"motivo": motivo, "monto": money(Decimal(pago["amount"]))})
    return {"pago_id": payment_id, "estado": "VOIDED"}


def occupancy(site_row: dict | None = None, tenant: dict | int | None = None) -> dict:
    s = site_row or site(tenant)
    occupied = query_one(
        "SELECT count(*) AS n FROM parking_stays WHERE site_id = ? AND status = 'ACTIVE'", (s["id"],))
    ocupados = occupied["n"] if occupied else 0
    por_tipo: dict[str, int] = {}
    for row in query(
        "SELECT t.code AS code, count(*) AS n FROM parking_stays s "
        "JOIN vehicles v ON v.id = s.vehicle_id JOIN vehicle_types t ON t.id = v.vehicle_type_id "
        "WHERE s.site_id = ? AND s.status = 'ACTIVE' GROUP BY t.code", (s["id"],)):
        por_tipo[row["code"]] = row["n"]
    capacidad = int(s["total_capacity"] or 0)
    return {"capacidad_total": capacidad, "ocupados": ocupados,
            "disponibles": max(0, capacidad - ocupados), "por_tipo": por_tipo}


# ── Comprobantes: numeración por sede dentro de la transacción ────────

def _issue_receipt_txn(conn, site_row: dict, receipt_type: str, stay_id=None,
                       payment_id=None, subscription_id=None, issued_by=None, token=None) -> dict:
    """Emite el recibo reservando el consecutivo de la sede (docs/05 §4)."""
    if receipt_type not in ("ENTRY", "EXIT", "SUBSCRIPTION", "ADJUSTMENT"):
        raise DomainError("Tipo de comprobante inválido.")
    # un EXIT exige stay_id (docs/11 §11.5)
    if receipt_type == "EXIT" and not stay_id:
        raise DomainError("Un recibo de salida exige la estadía asociada.")
    token = token or secrets.token_urlsafe(16)
    counter = conn.execute("SELECT next_number FROM receipt_counters WHERE site_id = ?",
                           (site_row["id"],)).fetchone()
    if not counter:
        conn.execute("INSERT INTO receipt_counters (site_id, next_number) VALUES (?, 1)", (site_row["id"],))
        numero = 1
    else:
        numero = int(counter["next_number"])
    conn.execute("UPDATE receipt_counters SET next_number = ? WHERE site_id = ?",
                 (numero + 1, site_row["id"]))
    conn.execute(
        "INSERT INTO receipts (site_id, tenant_id, payment_id, stay_id, receipt_number, receipt_type, issued_at, qr_payload) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (site_row["id"], site_row["tenant_id"], payment_id, stay_id, numero, receipt_type,
         time_utils.iso_utc(), token))
    receipt_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return {"id": receipt_id, "numero": numero, "tipo": receipt_type, "token": token}
