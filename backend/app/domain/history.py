"""Histórico y ocupación por hora (docs/05 §5).

El criterio temporal (entró antes de que terminara la hora y no había
salido) es ÚNICO para gráfico y detalle. Las franjas usan la hora
LOCAL del sitio, no UTC (docs/04 §4.5).
"""
from __future__ import annotations

from datetime import date, time, timedelta

from ..db import query
from . import time_utils
from .errors import DomainError
from .parking_operations import site

LIMITE_BUSQUEDA = 500


def search_history(user: dict, placa: str | None = None, desde: str | None = None,
                   hasta: str | None = None, estado: str | None = None,
                   tipo_vehiculo: str | None = None,
                   limite: int = LIMITE_BUSQUEDA) -> dict:
    """Búsqueda por placa/rango/estado/tipo; sin rango, sólo hoy (docs/04 §4.5).
    Aislamiento: sólo las estadías de la sede del tenant de la sesión."""
    site_row = site(user["tenant_id"])
    if desde and hasta and desde > hasta:
        raise DomainError("El rango de fechas es inválido: desde es posterior a hasta")
    limite = max(1, min(int(limite or LIMITE_BUSQUEDA), 5000))

    where = ["s.site_id = ?"]
    params: list = [site_row["id"]]
    if placa:
        parte = placa.upper().replace(" ", "")
        where.append("v.plate LIKE ?")
        params.append(f"%{parte}%")
    if estado:
        where.append("s.status = ?")
        params.append(estado.upper())
    if tipo_vehiculo:
        where.append("t.code = ?")
        params.append(tipo_vehiculo.upper())

    d_desde = time_utils.parse_date(desde) if desde else time_utils.today_for_site(site_row)
    d_hasta = time_utils.parse_date(hasta) if hasta else d_desde
    start, end = time_utils.utc_bounds_for_local_range(d_desde, d_hasta, site_row)
    where.append("s.entry_at >= ? AND s.entry_at < ?")
    params += [time_utils.iso_utc(start), time_utils.iso_utc(end)]

    rows = query(
        "SELECT s.id AS estadia_id, v.plate AS placa, t.name AS tipo_vehiculo, s.entry_at, s.exit_at, "
        "s.status, s.calculated_amount, p_entry.id AS recibo_ingreso_id, p_entry.receipt_number AS recib, "
        "r_exit.id AS recibo_salida_id "
        "FROM parking_stays s "
        "JOIN vehicles v ON v.id = s.vehicle_id "
        "JOIN vehicle_types t ON t.id = v.vehicle_type_id "
        "LEFT JOIN receipts p_entry ON p_entry.stay_id = s.id AND p_entry.receipt_type = 'ENTRY' "
        "LEFT JOIN receipts r_exit ON r_exit.stay_id = s.id AND r_exit.receipt_type = 'EXIT' "
        f"WHERE {' AND '.join(where)} ORDER BY s.entry_at DESC LIMIT ?",
        tuple(params) + (limite,))

    resultados = []
    for r in rows:
        entrada = time_utils.parse_iso(r["entry_at"])
        salida = time_utils.parse_iso(r["exit_at"])
        minutos = time_utils.elapsed_minutes(r["entry_at"], salida)
        resultados.append({
            "estadia_id": r["estadia_id"], "placa": r["placa"], "tipo_vehiculo": r["tipo_vehiculo"],
            "fecha_ingreso": time_utils.local_date_str(time_utils.local_date_of(entrada, site_row)),
            "hora_ingreso": time_utils.local_time_str(entrada, site_row),
            "fecha_salida": time_utils.local_date_str(time_utils.local_date_of(salida, site_row)) if salida else None,
            "hora_salida": time_utils.local_time_str(salida, site_row) if salida else "-",
            "estado": r["status"],
            "monto": f"{(r['calculated_amount'] or 0):.2f}",
            "duracion_minutos": minutos,
            "recibo_ingreso": {"id": r["recibo_ingreso_id"], "puede_reimprimir": bool(r["recibo_ingreso_id"])},
            "recibo_salida": {"id": r["recibo_salida_id"], "puede_reimprimir": bool(r["recibo_salida_id"])},
        })
    return {"total": len(resultados), "resultados": resultados,
            "limite_alcanzado": len(resultados) >= limite}


def _estadias_solapando_dia(site_row: dict, dia_local: date) -> list[tuple]:
    """Estadías solapando el día (docs/01: _stays_overlapping_day)."""
    start, end = time_utils.utc_bounds_for_local_range(dia_local, dia_local, site_row)
    rows = query(
        "SELECT s.id, s.entry_at, s.exit_at, v.vehicle_type_id, v.plate "
        "FROM parking_stays s JOIN vehicles v ON v.id = s.vehicle_id "
        "WHERE s.site_id = ? AND s.entry_at < ? AND (s.exit_at IS NULL OR s.exit_at > ?)",
        (site_row["id"], time_utils.iso_utc(end), time_utils.iso_utc(start)))
    return [(r["id"], time_utils.parse_iso(r["entry_at"]), time_utils.parse_iso(r["exit_at"]),
             r["vehicle_type_id"], r["plate"]) for r in rows]


def occupancy_by_hour(user: dict, fecha: str) -> dict:
    """Serie SIEMPRE de 24 puntos en hora local del sitio (docs/11 §11.4)."""
    site_row = site(user["tenant_id"])
    dia = time_utils.parse_date(fecha)
    estadias = _estadias_solapando_dia(site_row, dia)
    capacidad = int(site_row["total_capacity"] or 0)
    puntos = []
    maximo = 0
    for hora in range(24):
        fin = time_utils.local_boundary(site_row, dia, hora) + timedelta(hours=1)
        ocupados_t: dict[str, int] = {}
        for _id, entrada, salida, tipo_id, _placa in estadias:
            dentro_hora = entrada < fin and (salida is None or salida > fin)
            if dentro_hora:
                ocupados_t[tipo_id] = ocupados_t.get(tipo_id, 0) + 1
        total = sum(ocupados_t.values())
        maximo = max(maximo, total)
        puntos.append({"hora": hora, "ocupados": total, "por_tipo": ocupados_t})
    tipos = {r["id"]: r["code"] for r in query("SELECT id, code FROM vehicle_types")}
    for p in puntos:
        p["por_tipo"] = {tipos[k]: v for k, v in p["por_tipo"].items()}
    return {"fecha": fecha, "capacidad_total": capacidad, "puntos": puntos, "maximo": maximo}


def occupancy_detail(user: dict, fecha: str, hora: int) -> dict:
    """Detalle de una hora con EXACTAMENTE el mismo criterio del gráfico."""
    site_row = site(user["tenant_id"])
    if not isinstance(hora, int) or hora < 0 or hora > 23:
        raise DomainError("La hora debe estar entre 0 y 23.")
    dia = time_utils.parse_date(fecha)
    estadias = _estadias_solapando_dia(site_row, dia)
    fin = time_utils.local_boundary(site_row, dia, hora) + timedelta(hours=1)
    tipos = {r["id"]: (r["code"], r["name"]) for r in query("SELECT id, code, name FROM vehicle_types")}
    vehiculos = []
    for _id, entrada, salida, tipo_id, placa in estadias:
        if entrada < fin and (salida is None or salida > fin):
            ref = salida if salida else time_utils.utcnow()
            vehiculos.append({
                "estadia_id": _id, "placa": placa,
                "tipo_vehiculo": tipos.get(tipo_id, ("", ""))[1],
                "ingreso_local": time_utils.local_time_str(entrada, site_row),
                "horas_dentro": round((ref - entrada).total_seconds() / 3600.0, 1),
                "estado": "Dentro del parqueadero" if salida is None else "Cobrada",
            })
    vehiculos.sort(key=lambda v: v["ingreso_local"])
    return {"fecha": fecha, "hora": hora, "vehiculos": vehiculos}
