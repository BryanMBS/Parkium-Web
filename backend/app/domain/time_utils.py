"""Utilidades de tiempo: la fecha local del sitio gobierna todos los cálculos.

docs/05 §5 el original usa `today_for_site`, `_hora_local_utc` y
`utc_bounds_for_local_range`: el sistema ya piensa en zonas horarias
(`parking_sites.timezone`, por defecto America/Bogota, docs/12 §6).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from ..config import DEFAULT_SITE_TZ

ISO_FMT = "%Y-%m-%dT%H:%M:%S%z"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(dt: datetime | None = None) -> str:
    dt = dt or utcnow()
    return dt.isoformat(timespec="seconds")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:  # los datos viejos sin zona se interpretan como UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def site_tz(site: dict | None = None) -> ZoneInfo:
    try:
        if site and site.get("timezone"):
            return ZoneInfo(site["timezone"])
    except Exception:
        pass
    return DEFAULT_SITE_TZ


def today_for_site(site: dict | None = None) -> date:
    """Fecha civil del sitio (docs/05 §6: resolución ANTES de abrir transacción)."""
    return utcnow().astimezone(site_tz(site)).date()


def local_boundary(site: dict | None = None, day: date | None = None, hour: int | None = None) -> datetime:
    """Instante UTC de una hora local del sitio; p. ej. franja hora-H."""
    day = day or today_for_site(site)
    t = time(hour, 0) if hour is not None else time(0, 0)
    return datetime.combine(day, t, tzinfo=site_tz(site)).astimezone(timezone.utc)


def utc_bounds_for_local_range(
    desde: date, hasta: date, site: dict | None = None
) -> tuple[datetime, datetime]:
    """Rango UTC inclusivo de un rango civil local (docs/03 §3.9.2)."""
    if desde > hasta:
        raise ValueError("El rango es inválido: desde es posterior a hasta")
    start = local_boundary(site, desde, 0)
    end = local_boundary(site, hasta + timedelta(days=1), 0)
    return start, end


def local_str(dt: datetime | None, site: dict | None = None) -> str:
    """'2026-10-08 09:32' — horas en 24 h, docs/04 §4.5."""
    if dt is None:
        return "-"
    return dt.astimezone(site_tz(site)).strftime("%Y-%m-%d %H:%M")


def local_date_str(day: date) -> str:
    return day.strftime("%Y-%m-%d")


def local_time_str(dt: datetime | None, site: dict | None = None) -> str:
    if dt is None:
        return "-"
    return dt.astimezone(site_tz(site)).strftime("%H:%M")


def local_date_of(dt: datetime, site: dict | None = None) -> date:
    return dt.astimezone(site_tz(site)).date()


def elapsed_minutes(entry_at: str, exit_at: datetime | None = None) -> int:
    """Minutos transcurridos entre la entrada y la salida.

    docs/05 §7: en la web el reloj del servidor es la autoridad —
    el navegador nunca calcula tiempo.
    """
    entry = parse_iso(entry_at)
    exit_dt = exit_at or utcnow()
    if entry is None:
        return 0
    total = (exit_dt - entry).total_seconds() / 60.0
    return max(0, int(total))


def parse_date(value: str | None) -> date:
    """Parsea YYYY-MM-DD (contrato de API, docs/04 §4.1)."""
    if not value:
        raise ValueError("Fecha vacía")
    return date.fromisoformat(value[:10])
