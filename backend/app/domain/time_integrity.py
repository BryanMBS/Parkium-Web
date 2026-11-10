"""Seguridad del reloj (docs/05 §7) — el módulo de mayor riesgo.

La web difiere del original: el servidor ES la única autoridad de tiempo;
el cliente no calcula ni valida nada. El comportamiento declarado:
 infringe => retraso - el reloj producto 400 reloj_no_confiable;
reanclar tras una verificación exitosa externa (Preparación del Sprint 9.8).
"""
from __future__ import annotations

import threading
import urllib.error
import urllib.request
from datetime import timedelta

from ..config import settings
from ..db import execute, query_one, transaction
from . import time_utils
from .errors import ClockIntegrityError

TOLERANCIA_SEGUNDOS = 300.0  # 5 min de deriva considerada razonable
_BOOT_ID = f"web-{time_utils.iso_utc()}"


def _anchor() -> dict | None:
    return query_one("SELECT * FROM clock_anchors WHERE id = 1")


def _ensure_anchor() -> dict:
    """Crea el ancla del servidor al arrancar (docs/09 tarea 5.1)."""
    now = time_utils.utcnow()
    import time as _t
    with transaction() as conn:
        row = conn.execute("SELECT * FROM clock_anchors WHERE id = 1").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO clock_anchors (id, boot_id, boot_utc, boot_monotonic, last_trusted_utc, max_drift_seconds) "
                "VALUES (1, ?, ?, ?, ?, 0)",
                (_BOOT_ID, time_utils.iso_utc(now), _t.monotonic(), time_utils.iso_utc(now)))
            row = conn.execute("SELECT * FROM clock_anchors WHERE id = 1").fetchone()
        return dict(row)


def _drift_seconds() -> float:
    """Deriva del sistema contra el ancla; validación local del servidor."""
    import time as _t
    anchor = _ensure_anchor()
    boot_utc = time_utils.parse_iso(anchor["boot_utc"])
    if not boot_utc:
        return 0.0
    proyeccion = boot_utc + timedelta(seconds=_t.monotonic() - (anchor["boot_monotonic"] or 0))
    return (time_utils.utcnow() - proyeccion).total_seconds()


def verify_clock(usar_red: bool = False) -> dict:
    """Verifica la hora; regla y deriva quedan en clock_checks (docs/09 5.6)."""
    system = time_utils.utcnow()
    reference = None
    source = "SISTEMA"
    message = "Hora del servidor verificada contra el ancla persistente."
    drift = _drift_seconds()
    suspicious = abs(drift) > TOLERANCIA_SEGUNDOS

    if usar_red:
        ref, fuente_red = _network_reference()
        if ref:
            reference = ref
            source = "FUENTE_EXTERNA"
            drift_red = (system - ref).total_seconds()
            suspicious = abs(drift_red) > TOLERANCIA_SEGUNDOS
            message = "Hora verificada contra una fuente externa."
            if abs(drift_red) <= TOLERANCIA_SEGUNDOS:
                _reanchor()
        else:
            source = "FUENTE_EXTERNA_NO_DISPONIBLE"
            message = "La fuente externa no respondió; la verificación local sigue siendo válida."
            suspicious = abs(drift) > TOLERANCIA_SEGUNDOS
    execute(
        "INSERT INTO clock_checks (checked_at, source, system_utc, reference_utc, drift_seconds, is_suspicious, message) "
        "VALUES (?,?,?,?,?,?,?)",
        (time_utils.iso_utc(), source, time_utils.iso_utc(system),
         time_utils.iso_utc(reference) if reference else None,
         drift if not reference else (system - reference).total_seconds(),
         1 if suspicious else 0, message))
    if suspicious:
        raise ClockIntegrityError(f"Deriva de {drift:+.0f} s: no se puede cobrar hasta reanclar.")
    return _status()


def _reanchor() -> None:
    """Reancla boot_utc/boot_monotonic desde ahora (docs/09 tarea 5.5)."""
    import time as _t
    execute(
        "UPDATE clock_anchors SET boot_id = ?, boot_utc = ?, boot_monotonic = ?, last_trusted_utc = ? WHERE id = 1",
        (_BOOT_ID, time_utils.iso_utc(), _t.monotonic(), time_utils.iso_utc()))


def check_before_billing(user: dict) -> dict:
    """Obligatorio en cada cotización y cada cobro (docs/05 §7)."""
    return verify_clock(usar_red=False)


def clock_status_summary() -> dict:
    try:
        return _status()
    except ClockIntegrityError:
        return _status(bloqueado=True)


def _status(bloqueado: bool = False) -> dict:
    anchor = _anchor() or {}
    last = query_one("SELECT * FROM clock_checks ORDER BY id DESC LIMIT 1")
    checks = query_one("SELECT count(*) AS n FROM clock_checks WHERE is_suspicious = 1")
    drift = round(_drift_seconds(), 1)
    signo = "+" if drift >= 0 else ""
    texto = f"{signo}{drift:.0f} s"
    return {
        "ok": not bloqueado,
        "verificada": bool(anchor.get("last_trusted_utc")) and not bloqueado,
        "fuente": last["source"] if last else "SISTEMA",
        "hora_sistema": time_utils.iso_utc(),
        "hora_referencia": anchor.get("last_trusted_utc"),
        "deriva_segundos": drift,
        "deriva_texto": texto,
        "verificaciones_sospechosas": checks["n"] if checks else 0,
        "mensaje": "El cobro está bloqueado: verifique la hora para reanclar." if bloqueado
        else "Hora verificada contra el ancla del servidor.",
    }


def _network_reference() -> tuple | None:
    """Cabecera HTTP Date de la fuente externa, en hilo con espera máxima
    (docs/05 §7; docs/12 §10: sin red el cobro SIGUE funcionando)."""
    result: dict = {}

    def _run():
        try:
            req = urllib.request.Request(settings.url_fuente_hora, method="HEAD")
            with urllib.request.urlopen(req, timeout=settings.espera_maxima_fuente_hora) as resp:
                fecha = resp.headers.get("Date")
                if fecha:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(fecha)
                    if dt.tzinfo is None:
                        from datetime import timezone
                        dt = dt.replace(tzinfo=timezone.utc)
                    result["dt"] = dt.astimezone(time_utils.utcnow().tzinfo)
        except (urllib.error.URLError, OSError, ValueError):
            pass

    hilo = threading.Thread(target=_run, daemon=True)
    hilo.start()
    hilo.join(settings.espera_maxima_fuente_hora)
    return (result.get("dt"), "FUENTE_EXTERNA") if result.get("dt") else None
