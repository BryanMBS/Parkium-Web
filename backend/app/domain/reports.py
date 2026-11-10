"""Reportes y exportaciones (docs/05 §9, 04 §4.9).

El consolidado es SÓLO super administrador (`_require_report_access`);
el dashboard lo ven ADMIN y OPERATOR. Los importes viajan como cadena.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from ..db import query, query_one
from . import authentication as auth, time_utils
from .errors import AuthorizationError
from .parking_operations import money, site, occupancy


def _require_report_access(user: dict) -> None:
    # require_superadmin no acepta mensaje propio; require_role sí (docs/07 §7.1)
    auth.require_role(user, [auth.ROLE_SUPERADMIN],
                      "Sólo el super administrador ve los reportes consolidados.")


def dashboard_summary(user: dict) -> dict:
    """Ocupación, ingresos del día y cupo disponible — admin y operador.
    Todos los agregados filtran por el tenant de la sesión."""
    site_row = site(user["tenant_id"])
    tid = user["tenant_id"]
    tz_cache = {"timezone": site_row["timezone"]}
    start, end = time_utils.utc_bounds_for_local_range(
        time_utils.today_for_site(site_row), time_utils.today_for_site(site_row), site_row)
    today = query_one(
        "SELECT COALESCE(SUM(amount), 0) AS ingresos, count(*) AS pagos FROM payments "
        "WHERE status = 'APPROVED' AND tenant_id = ? AND paid_at >= ? AND paid_at < ?",
        (tid, time_utils.iso_utc(start), time_utils.iso_utc(end)))
    salidas = query_one(
        "SELECT count(*) AS n FROM parking_stays WHERE site_id = ? AND exit_at >= ? AND exit_at < ? "
        "AND status = 'PAID'",
        (site_row["id"], time_utils.iso_utc(start), time_utils.iso_utc(end)))
    mensualidades = query_one(
        "SELECT COALESCE(SUM(amount), 0) AS n FROM payments WHERE status = 'APPROVED' "
        "AND tenant_id = ? AND subscription_id IS NOT NULL AND paid_at >= ? AND paid_at < ?",
        (tid, time_utils.iso_utc(start), time_utils.iso_utc(end)))
    return {
        "ocupacion": occupancy(site_row),
        "hoy": {
            "ingresos": money(Decimal(str((today or {}).get("ingresos") or 0))),
            "salidas_cobradas": (salidas or {}).get("n", 0),
            "mensualidades": money(Decimal(str((mensualidades or {}).get("n") or 0))),
        },
        "generado_en": time_utils.iso_utc(),
    }


def operation_summary(user: dict, desde: str | None = None, hasta: str | None = None) -> dict:
    """Consolidado por rango — sólo super admin (docs/01 §1.2)."""
    _require_report_access(user)
    site_row = site(user["tenant_id"])
    tid = user["tenant_id"]
    hoy = time_utils.today_for_site(site_row)
    d_hasta = time_utils.parse_date(hasta) if hasta else hoy
    d_desde = time_utils.parse_date(desde) if desde else d_hasta - timedelta(days=30)
    start, end = time_utils.utc_bounds_for_local_range(d_desde, d_hasta, site_row)
    base_params = (tid, time_utils.iso_utc(start), time_utils.iso_utc(end))
    # fix UX-D001: en multi-tenant payments/stays/vehicles/users/tariff_plans tienen tenant_id;
    # se califica con alias p para evitar "ambiguous column name" al hacer JOIN.
    t_sql = "p.tenant_id = ? AND p.paid_at >= ? AND p.paid_at < ?"

    rotacion = query_one(
        "SELECT COALESCE(SUM(p.amount), 0) AS n FROM payments p "
        f"WHERE p.status = 'APPROVED' AND {t_sql}",
        base_params)
    mensualidades = query_one(
        "SELECT COALESCE(SUM(p.amount), 0) AS n FROM payments p "
        f"WHERE p.status = 'APPROVED' AND p.subscription_id IS NOT NULL AND {t_sql}", base_params)
    por_metodo = query(
        "SELECT m.name AS etiqueta, COALESCE(SUM(p.amount), 0) AS valor, count(*) AS cantidad "
        "FROM payments p JOIN payment_methods m ON m.id = p.payment_method_id "
        f"WHERE p.status = 'APPROVED' AND {t_sql} GROUP BY m.id ORDER BY m.id",
        base_params)
    por_tipo = query(
        "SELECT t.name AS etiqueta, COALESCE(SUM(p.amount), 0) AS valor, count(*) AS cantidad "
        "FROM payments p JOIN parking_stays s ON s.id = p.stay_id "
        "JOIN vehicles v ON v.id = s.vehicle_id JOIN vehicle_types t ON t.id = v.vehicle_type_id "
        f"WHERE p.status = 'APPROVED' AND {t_sql} GROUP BY t.id",
        base_params)
    por_empleado = query(
        "SELECT u.full_name AS etiqueta, COALESCE(SUM(p.amount), 0) AS valor, count(*) AS cantidad "
        "FROM payments p JOIN users u ON u.id = p.received_by_user_id "
        f"WHERE p.status = 'APPROVED' AND {t_sql} GROUP BY u.id",
        base_params)
    por_tarifa = query(
        "SELECT t.name AS etiqueta, COALESCE(SUM(p.amount), 0) AS valor, count(*) AS cantidad "
        "FROM payments p JOIN parking_stays s ON s.id = p.stay_id "
        "JOIN tariff_plans t ON t.id = s.tariff_plan_id "
        f"WHERE p.status = 'APPROVED' AND {t_sql} GROUP BY t.id "
        "ORDER BY t.name",
        base_params)  # docs/04 §4.9: la estadía recuerda el plan con el que entró
    return {
        "desde": d_desde.isoformat(), "hasta": d_hasta.isoformat(),
        "rotacion": money(Decimal(str((rotacion or {"n": 0})["n"]))),
        "mensualidades": money(Decimal(str((mensualidades or {"n": 0})["n"]))),
        "total": money(Decimal(str((rotacion or {"n": 0})["n"]))),
        "por_metodo": [{"etiqueta": r["etiqueta"], "valor": money(Decimal(str(r["valor"]))),
                        "cantidad": r["cantidad"]} for r in por_metodo],
        "por_tipo_vehiculo": [{"etiqueta": r["etiqueta"], "valor": money(Decimal(str(r["valor"]))),
                               "cantidad": r["cantidad"]} for r in por_tipo],
        "por_empleado": [{"etiqueta": r["etiqueta"], "valor": money(Decimal(str(r["valor"]))),
                          "cantidad": r["cantidad"]} for r in por_empleado],
        "por_tarifa": [{"etiqueta": r["etiqueta"], "valor": money(Decimal(str(r["valor"]))),
                        "cantidad": r["cantidad"]} for r in por_tarifa],
    }


def export_csv(user: dict, desde=None, hasta=None) -> str:
    data = operation_summary(user, desde, hasta)
    buf = io.StringIO()
    # UTF-8 con BOM se añade en la respuesta (docs/05 §9)
    buf.write("\ufeff")
    w = csv.writer(buf)
    w.writerow(["Resumen", data["desde"], data["hasta"]])
    w.writerow(["Rotación (estadías)", data["rotacion"]])
    w.writerow(["Mensualidades", data["mensualidades"]])
    w.writerow(["Total", data["total"]])
    w.writerow([])
    w.writerow("Por forma de pago;;".split(";"))
    for r in data["por_metodo"]:
        w.writerow([r["etiqueta"], r["valor"], r["cantidad"]])
    return buf.getvalue()


def export_json(user: dict, desde=None, hasta=None) -> str:
    return json.dumps(operation_summary(user, desde, hasta), ensure_ascii=False, indent=2)
