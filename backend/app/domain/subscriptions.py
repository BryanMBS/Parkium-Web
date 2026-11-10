"""Mensualidades y convenios (docs/05 §6, 04 §4.6).

Reglas verificadas: estado derivado de la fecha (nunca de la columna),
alta exige >= 1 placa, horario con ambas horas o ninguna, renovación
crea período + cobro en UNA transacción, fin de mes real con bisiesto,
y la fecha del sitio se resuelve antes de abrir la transacción
(docs/05 §6: el bloqueo de 33 s del original).
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal

from ..db import execute, query, query_one, transaction
from . import authentication as auth, time_utils
from .errors import AuthorizationError, ConflictError, DomainError, NotFoundError
from .parking_operations import normalise_plate, money, site, _tid


def _month_end(start: date, months: int) -> date:
    """Fin de mes real: 31/01 + 1 mes = 28/02 (29 en bisiesto) (docs/11 §11.2)."""
    mes = start.month - 1 + months
    anio = start.year + mes // 12
    mes = mes % 12 + 1
    dia = min(start.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)


def _effective_status(sub: dict, site_row: dict) -> tuple[str, int]:
    """El estado se DERIVA de la fecha, no de la columna (docs/03 §3.5)."""
    hoy = time_utils.today_for_site(site_row)
    if sub["status"] == "CANCELLED":
        return "CANCELLED", 0
    vence = time_utils.parse_date(sub["expires_on"])
    dias = (vence - hoy).days
    if dias < 0:
        return "EXPIRED", dias
    if dias <= 7:
        return "EXPIRING", dias
    return "ACTIVE", dias


ESTADO_TEXTO = {
    "ACTIVE": "VIGENTE", "EXPIRING": "POR VENCER", "EXPIRED": "VENCIDA",
    "CANCELLED": "CANCELADA", "NO_PLAN": "SIN PLAN",
}


def create_customer(user: dict, datos: dict, ip=None) -> dict:
    auth.require_admin(user)
    tid = _tid(user)
    nombre = (datos.get("nombre") or "").strip()
    if not nombre:
        raise DomainError("El nombre del cliente es obligatorio.")
    doc_tipo, doc_num = datos.get("documento", {}).get("tipo"), datos.get("documento", {}).get("numero")
    # el documento de identidad es de la persona: unicidad GLOBAL (decisión M1)
    if doc_num and query_one(
            "SELECT id FROM customers WHERE document_number = ? AND document_type IS ?",
            (doc_num, doc_tipo)):
        raise ConflictError("Ya existe un cliente con ese documento.")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO customers (tenant_id, document_type, document_number, full_name, email, phone, address) "
            "VALUES (?,?,?,?,?,?,?)",
            (tid, doc_tipo, doc_num, nombre, datos.get("correo"), datos.get("telefono"),
             datos.get("direccion")))
        cliente_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        for placa_raw in datos.get("placas", []) or []:
            _attach_vehicle_txn(conn, user, cliente_id, placa_raw)
        auth._audit(conn, user["id"], "customer", cliente_id, "CUSTOMER_CREATED", None,
                    {"nombre": nombre, "documento": doc_num}, ip)
    return customer_detail(cliente_id, tid)


def _attach_vehicle_txn(conn, user: dict, cliente_id: int, placa_raw: str) -> str:
    tid = _tid(user)
    plate = normalise_plate(placa_raw)
    veh = conn.execute("SELECT * FROM vehicles WHERE plate = ? AND tenant_id = ?",
                       (plate, tid)).fetchone()
    if veh:
        data = dict(veh)
        if data["customer_id"] and data["customer_id"] != cliente_id:
            raise ConflictError(f"La placa {plate} ya pertenece a otro cliente.")
        conn.execute("UPDATE vehicles SET customer_id = ? WHERE id = ?", (cliente_id, data["id"]))
        vehicle_id = data["id"]
    else:
        conn.execute(
            "INSERT INTO vehicles (tenant_id, plate, vehicle_type_id, customer_id) VALUES (?,?,?,?)",
            (tid, plate, 1, cliente_id))
        vehicle_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    auth._audit(conn, user["id"], "vehicle", vehicle_id, "VEHICLE_ATTACHED", None,
                {"placa": plate, "cliente_id": cliente_id})
    return plate


def attach_vehicle(user: dict, cliente_id: int, placa: str, ip=None) -> str:
    auth.require_admin(user)
    tid = _tid(user)
    if not query_one("SELECT id FROM customers WHERE id = ? AND tenant_id = ?",
                     (cliente_id, tid)):
        raise NotFoundError()
    with transaction() as conn:
        plate = _attach_vehicle_txn(conn, user, cliente_id, placa)
    return plate


def customer_vehicles(cliente_id: int, tenant_id: int | None = None) -> list[dict]:
    if tenant_id is None:
        raise AuthorizationError("La búsqueda exige el tenant de la sesión.")
    return query("SELECT * FROM vehicles WHERE customer_id = ? AND tenant_id = ? ORDER BY plate",
                 (cliente_id, tenant_id))


def customer_detail(cliente_id: int, tenant_id: int | None = None) -> dict | None:
    if tenant_id is None:
        raise AuthorizationError("La consulta exige el tenant de la sesión.")
    cliente = query_one("SELECT * FROM customers WHERE id = ? AND tenant_id = ?",
                        (cliente_id, tenant_id))
    if not cliente:
        raise NotFoundError()
    cliente["placas"] = [v["plate"] for v in customer_vehicles(cliente_id, tenant_id)]
    return cliente


def create_subscription(user: dict, datos: dict, ip=None) -> dict:
    """Alta de mensualidad: exige >= 1 placa (docs/11 §11.2)."""
    auth.require_admin(user)
    tid = _tid(user)
    site_row = site(tid)
    cliente_id = datos.get("cliente_id")
    if not query_one("SELECT id FROM customers WHERE id = ? AND tenant_id = ?",
                     (cliente_id, tid)):
        raise NotFoundError("El cliente no existe en este tenant.")
    placas = [normalise_plate(p) for p in (datos.get("placas") or [])]
    if not placas:
        raise DomainError("La mensualidad exige al menos una placa.")
    horario = datos.get("horario") or {}
    desde_h, hasta_h = horario.get("desde"), horario.get("hasta")
    if bool(desde_h) != bool(hasta_h):
        raise DomainError("El horario permitido exige ambas horas o ninguna.")
    inicio = time_utils.parse_date(datos["inicio"])
    meses = int(datos.get("meses") or 1)
    vence = _month_end(inicio, meses)
    valor = Decimal(str(datos["valor"] or 0))
    with transaction() as conn:
        conn.execute(
            "INSERT INTO subscriptions (site_id, tenant_id, customer_id, plan_name, starts_on, expires_on, "
            "amount, permitted_start, permitted_end, status) VALUES (?,?,?,?,?,?,?,?,?, 'ACTIVE')",
            (site_row["id"], tid, cliente_id, datos["plan"], inicio.isoformat(), vence.isoformat(),
             valor, desde_h, hasta_h))
        sub_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        for placa_raw in placas:
            veh = conn.execute("SELECT id FROM vehicles WHERE plate = ? AND tenant_id = ?",
                               (placa_raw, tid)).fetchone()
            if not veh:
                conn.execute(
                    "INSERT INTO vehicles (tenant_id, plate, vehicle_type_id, customer_id) VALUES (?,?,?,?)",
                    (tid, placa_raw, 1, cliente_id))
                veh = conn.execute("SELECT id FROM vehicles WHERE plate = ? AND tenant_id = ?",
                                   (placa_raw, tid)).fetchone()
            conn.execute(
                "INSERT OR IGNORE INTO subscription_vehicles (subscription_id, vehicle_id) VALUES (?,?)",
                (sub_id, veh["id"]))
        auth._audit(conn, user["id"], "subscription", sub_id, "SUBSCRIPTION_CREATED", None,
                    {"plan": datos["plan"], "placas": placas, "vence": vence.isoformat()}, ip)
    return get_subscription(sub_id, tid)


def get_subscription(sub_id: int, tenant_id: int | None = None) -> dict | None:
    """Con tenant_id exige pertenencia (los ids son globales)."""
    if tenant_id is None:
        sub = query_one("SELECT * FROM subscriptions WHERE id = ?", (sub_id,))
    else:
        sub = query_one("SELECT * FROM subscriptions WHERE id = ? AND tenant_id = ?",
                        (sub_id, tenant_id))
    if not sub:
        raise NotFoundError()
    site_row = query_one("SELECT * FROM parking_sites WHERE id = ?", (sub["site_id"],))
    estado, dias = _effective_status(sub, site_row)
    tid = tenant_id if tenant_id is not None else sub["tenant_id"]
    pagado = query_one(
        "SELECT COALESCE(SUM(amount), 0) AS n FROM payments "
        "WHERE subscription_id = ? AND tenant_id = ? AND status = 'APPROVED'", (sub_id, tid))
    pagado_d = Decimal(str((pagado or {"n": 0})["n"]))
    saldo = max(Decimal("0"), Decimal(sub["amount"]) - pagado_d)
    placas = [v["plate"] for v in query(
        "SELECT v.plate FROM vehicles v JOIN subscription_vehicles sv ON sv.vehicle_id = v.id "
        "WHERE sv.subscription_id = ? ORDER BY v.plate", (sub_id,))]
    return {**sub, "estado": estado, "estado_texto": ESTADO_TEXTO[estado],
            "dias_restantes": dias, "pagado": money(pagado_d), "saldo": money(saldo), "placas": placas}


def portfolio(user: dict, q: str | None = None, estado: str | None = None,
              solo_saldo: bool = False) -> dict:
    """Listado por cliente con estado y saldo (docs/04 §4.6)."""
    auth.require_admin(user)
    tid = _tid(user)
    site_row = site(tid)
    if estado and estado in ESTADO_TEXTO.values():
        estado = [k for k, v in ESTADO_TEXTO.items() if v == estado.upper()][0]
    clientes = query(
        "SELECT c.*, s.id AS suscripcion_id, s.plan_name, s.starts_on, s.expires_on, "
        "s.amount, s.status, s.permitted_start, s.permitted_end "
        "FROM customers c LEFT JOIN subscriptions s ON s.customer_id = c.id AND s.tenant_id = c.tenant_id "
        "AND s.id = (SELECT id FROM subscriptions WHERE customer_id = c.id "
        "ORDER BY created_at DESC LIMIT 1) WHERE c.tenant_id = ? ORDER BY c.full_name", (tid,))
    salida = []
    for c in clientes:
        if q:
            placas = [v["plate"] for v in query(
                "SELECT plate FROM vehicles WHERE customer_id = ? AND tenant_id = ?",
                (c["id"], tid))]
            q_up = q.upper()
            match = (q_up in (c["full_name"] or "").upper()
                     or q_up in (c["document_number"] or "").upper()
                     or q_up in (c["phone"] or "").upper()
                     or any(q_up in p for p in placas))
            if not match:
                continue
        if c["suscripcion_id"]:
            sub = get_subscription(c["suscripcion_id"])
            estado_val, texto, dias = sub["estado"], sub["estado_texto"], sub["dias_restantes"]
            valor, pagado, saldo = sub["amount"], sub["pagado"], sub["saldo"]
        else:
            estado_val, texto, dias = "NO_PLAN", "SIN PLAN", None
            valor, pagado, saldo = "-", "-", "-"
        if estado and estado_val != estado:
            continue
        if solo_saldo and saldo in ("-", "0.00"):
            continue
        salida.append({
            "cliente_id": c["id"], "nombre": c["full_name"],
            "documento": {"tipo": c["document_type"], "numero": c["document_number"]},
            "telefono": c["phone"], "correo": c["email"],
            "placas": [v["plate"] for v in query(
                "SELECT plate FROM vehicles WHERE customer_id = ? AND tenant_id = ? "
                "ORDER BY plate", (c["id"], tid))],
            "suscripcion_id": c["suscripcion_id"], "plan": c["plan_name"],
            "inicio": c["starts_on"], "vence": c["expires_on"],
            "estado": estado_val, "estado_texto": texto, "dias_restantes": dias,
            "valor": valor, "pagado": pagado, "saldo": saldo,
        })
    return {"total": len(salida), "clientes": salida}


def pay_subscription(user: dict, sub_id: int, metodo: str, monto: str,
                     efectivo_recibido: str | None = None, referencia: str | None = None,
                     ip=None) -> dict:
    """Cobro de saldo de una mensualidad (docs/04 §4.6)."""
    return _subscription_cash(user, sub_id, "SUBSCRIPTION_PAYMENT", metodo, monto,
                              efectivo_recibido, referencia, None, None, ip)


def renew_subscription(user: dict, sub_id: int, metodo: str, monto: str, meses: int = 1,
                       efectivo_recibido: str | None = None, referencia: str | None = None,
                       ip=None) -> dict:
    """Renovación: período + cobro en UNA transacción (docs/04 §6)."""
    tid = _tid(user)
    sub = get_subscription(sub_id, tid)
    vence_actual = time_utils.parse_date(sub["expires_on"])
    hoy = time_utils.today_for_site(site(tid))
    inicio_nuevo = vence_actual + __import__("datetime").timedelta(days=1) if vence_actual >= hoy else hoy
    vence_nuevo = _month_end(inicio_nuevo, int(meses or 1))
    resultado = _subscription_cash(user, sub_id, "SUBSCRIPTION_RENEWED", metodo, monto,
                                   efectivo_recibido, referencia,
                                   (inicio_nuevo, vence_nuevo), sub, ip)
    return {"suscripcion_anterior": sub_id, "suscripcion_nueva": resultado["suscripcion_nueva"],
            "pago_id": resultado["pago_id"],
            "inicio": inicio_nuevo.isoformat(), "vence": vence_nuevo.isoformat(),
            "recibo": resultado.get("recibo")}


def _subscription_cash(user, sub_id, accion, metodo, monto, efectivo_recibido,
                       referencia, periodo, sub_previa, ip=None) -> dict:
    from .parking_operations import money as _m
    metodo_up = (metodo or "").upper()
    if metodo_up != "CASH" and efectivo_recibido:
        raise DomainError("Sólo CASH registra efectivo recibido y cambio.")
    valor = Decimal(str(monto)) if monto else D0_VAL
    tid = _tid(user)
    site_row = site(tid)
    lautc = time_utils.utcnow()
    with transaction() as conn:
        turno = conn.execute(
            "SELECT id FROM cash_shifts WHERE user_id = ? AND site_id = ? AND tenant_id = ? AND status = 'OPEN' "
            "ORDER BY opened_at DESC LIMIT 1", (user["id"], site_row["id"], tid)).fetchone()
        if metodo_up == "CASH":
            if not turno:
                raise DomainError("Cobro en efectivo rechazado: no hay un turno de caja abierto.")
            if efectivo_recibido is None:
                raise DomainError("Registre el efectivo recibido.")
            recibido, cambio = Decimal(str(efectivo_recibido)), Decimal(str(efectivo_recibido)) - valor
            if cambio < 0:
                raise DomainError(f"Faltan ${money(valor - recibido)}")
        else:
            recibido = cambio = None
        sub = conn.execute("SELECT * FROM subscriptions WHERE id = ? AND tenant_id = ?",
                           (sub_id, tid)).fetchone()
        if not sub:
            raise NotFoundError()
        sub = dict(sub)
        nueva_id = None
        if periodo:
            inicio_nuevo, vence_nuevo = periodo
            conn.execute(
                "UPDATE subscriptions SET status = 'ACTIVE' WHERE id = ? AND tenant_id = ? AND status = 'ACTIVE'",
                (sub_id, tid))
            conn.execute(
                "UPDATE subscriptions SET status = 'EXPIRED' WHERE id = ? AND tenant_id = ? "
                "AND expires_on < date('now')",
                (sub_id, tid))
            conn.execute(
                "INSERT INTO subscriptions (site_id, tenant_id, customer_id, plan_name, starts_on, expires_on, "
                "amount, permitted_start, permitted_end, status) VALUES (?,?,?,?,?,?,?,?,?, 'ACTIVE')",
                (sub["site_id"], sub["tenant_id"], sub["customer_id"], sub["plan_name"],
                 inicio_nuevo.isoformat(), vence_nuevo.isoformat(), sub["amount"],
                 sub["permitted_start"], sub["permitted_end"]))
            nueva_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
            for v in conn.execute(
                    "SELECT vehicle_id FROM subscription_vehicles WHERE subscription_id = ?",
                    (sub_id,)).fetchall():
                conn.execute(
                    "INSERT OR IGNORE INTO subscription_vehicles (subscription_id, vehicle_id) VALUES (?,?)",
                    (nueva_id, v["vehicle_id"]))
        method_row = conn.execute("SELECT id FROM payment_methods WHERE code = ?", (metodo_up,)).fetchone()
        if not method_row:
            raise DomainError("Forma de pago inválida.")
        conn.execute(
            "INSERT INTO payments (tenant_id, subscription_id, cash_shift_id, payment_method_id, "
            "received_by_user_id, amount, amount_received, change_amount, paid_at, external_reference, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?, 'APPROVED')",
            (tid, sub_id, turno["id"] if turno else None, method_row["id"], user["id"], valor,
             recibido, cambio, time_utils.iso_utc(lautc), referencia))
        pago_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        receipt = _subscription_receipt(conn, site_row, sub_id, pago_id, valor, user["id"])
        auth._audit(conn, user["id"], "subscription", sub_id, accion, None,
                    {"monto": money(valor), "metodo": metodo_up}, ip)
    return {"pago_id": pago_id, "suscripcion_nueva": nueva_id or sub_id,
            "recibo": receipt, "monto": money(valor)}


D0_VAL = Decimal("0")


def _subscription_receipt(conn, site_row, sub_id, pago_id, valor, user_id) -> dict:
    from .parking_operations import _issue_receipt_txn
    return _issue_receipt_txn(conn, site_row, receipt_type="SUBSCRIPTION", payment_id=pago_id,
                              issued_by=user_id)


def cancel_subscription(user: dict, sub_id: int, motivo: str, ip=None) -> dict:
    """Cancelar CONSERVA el historial de pagos (docs/05 §6)."""
    auth.require_admin(user)
    tid = _tid(user)
    with transaction() as conn:
        cur = conn.execute(
            "UPDATE subscriptions SET status = 'CANCELLED' WHERE id = ? AND tenant_id = ?",
            (sub_id, tid))
        if not cur.rowcount:
            raise NotFoundError()
        auth._audit(conn, user["id"], "subscription", sub_id, "SUBSCRIPTION_CANCELLED",
                    {"estado": "ACTIVE"}, {"estado": "CANCELLED", "motivo": motivo}, ip)
    return get_subscription(sub_id, tid)


def subscription_alerts(user: dict, dias_aviso: int = 7) -> list[dict]:
    """Planes por vencer o vencidos CON saldo (docs/04 §4.6)."""
    cartera = portfolio(user)["clientes"]
    alertas = []
    for c in cartera:
        if c["estado"] in ("EXPIRING", "EXPIRED") and c["saldo"] not in ("-", "0.00"):
            alertas.append({**c, "status": "POR VENCER" if c["estado"] == "EXPIRING" else "VENCIDA"})
    return alertas


def create_agreement(user: dict, datos: dict, ip=None) -> dict:
    auth.require_admin(user)
    tid = _tid(user)
    site_row = site(tid)
    cliente_id = datos.get("cliente_id")
    if not query_one("SELECT id FROM customers WHERE id = ? AND tenant_id = ?",
                     (cliente_id, tid)):
        raise NotFoundError("El cliente no existe en este tenant.")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO agreements (site_id, customer_id, name, discount_type, discount_value, valid_from, valid_until) "
            "VALUES (?,?,?,?,?,?,?)",
            (site_row["id"], cliente_id, datos["nombre"], datos["tipo_descuento"],
             Decimal(str(datos["valor"] or 0)), datos["valido_desde"], datos.get("valido_hasta")))
        ag_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        auth._audit(conn, user["id"], "agreement", ag_id, "AGREEMENT_CREATED", None,
                    {"nombre": datos["nombre"]}, ip)
    return {"id": ag_id}
