"""Dominio multi-tenant: la tabla `tenants` y sus cuotas de plan (Fase 1).

- `tenants` es la RAÍZ del aislamiento; todo lo demás cuelga de `tenant_id`.
- Los estados son ACTIVE | SUSPENDED; los planes BASIC | PRO | ENTERPRISE
  (docs a definir: este módulo es nuevo, no portado del escritorio).
- El tenant del usuario SIEMPRE se toma del servidor (sesión), nunca del
  body ni de la URL (paso 0 del plan multi-tenant).
"""
from __future__ import annotations

import json
from decimal import Decimal

from ..db import execute, query, query_one, transaction
from .errors import ConflictError, DomainError, PlanLimitError
from .time_utils import iso_utc

PLANES = ("BASIC", "PRO", "ENTERPRISE")
ESTADOS = ("ACTIVE", "SUSPENDED")


def get_tenant(tenant_id: int) -> dict | None:
    return query_one("SELECT * FROM tenants WHERE id = ?", (tenant_id,))


def tenant_by_nit(nit: str) -> dict | None:
    return query_one("SELECT * FROM tenants WHERE nit = ?", (nit.strip(),))


def tenant_by_name(name: str) -> dict | None:
    return query_one("SELECT * FROM tenants WHERE LOWER(name) = LOWER(?)", (name.strip(),))


def crear_tenant(name: str, nit: str, plan: str, max_sites: int, max_users: int,
                 billing_cutoff_day: int, actor: dict | None = None,
                 conn=None) -> int:
    """Crea el tenant. Con `conn` (transacción de plataforma) no abre la suya:
    así tenant + primera sede + primer admin viajan en UNA transacción."""
    name = (name or "").strip()
    nit = (nit or "").strip()
    if not name:
        raise DomainError("El nombre del cliente es obligatorio.")
    if not nit or not _nit_colombiano_valido(nit):
        raise DomainError("NIT inválido.", {"nit": nit})
    if plan not in PLANES:
        raise DomainError("Plan desconocido.", {"plan": plan})
    if not 1 <= int(max_sites) <= 999 or not 1 <= int(max_users) <= 999:
        raise DomainError("Los límites deben estar entre 1 y 999.")
    if not 1 <= int(billing_cutoff_day) <= 28:
        raise DomainError("El día de corte debe ser 1–28.")
    if tenant_by_nit(nit):
        raise ConflictError("Ya existe un cliente con ese NIT.", {"nit": nit})
    if tenant_by_name(name):
        raise ConflictError("Ya existe un cliente con ese nombre.", {"name": name})
    sql = ("INSERT INTO tenants (name, nit, status, plan, max_sites, max_users, "
           "billing_cutoff_day, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)")
    params = (name, nit, "ACTIVE", plan, int(max_sites), int(max_users),
              int(billing_cutoff_day), iso_utc(), iso_utc())
    if conn is not None:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)
    with transaction() as cn:
        return int(cn.execute(sql, params).lastrowid or 0)


def _nit_colombiano_valido(nit: str) -> bool:
    """Formato colombiano: 9-10 dígitos con dígito de verificación opcional
    `900123456-7`. Verifica el módulo 15 (algoritmo DIAN)."""
    cuerpo, sep, dv = nit.partition("-")
    if not cuerpo.isdigit() or not (7 <= len(cuerpo) <= 11):
        return False
    if not dv:
        return True
    if not dv.isdigit() or len(dv) != 1:
        return False
    fases = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53)
    suma = sum(int(d) * fases[i] for i, d in enumerate(reversed(cuerpo[:12])))
    r = suma % 11
    esperado = (11 - r) if r > 1 else r
    return int(dv) == esperado


def suspender(tenant_id: int, motivo: str, actor) -> None:
    """Suspende al tenant y revoca TODAS sus sesiones activas en la misma
    transacción (la sesión también muere en la siguiente petición por el
    chequeo de estado en validate_session)."""
    if not (motivo or "").strip():
        raise DomainError("El motivo es obligatorio para suspender.")
    with transaction() as conn:
        conn.execute(
            "UPDATE tenants SET status='SUSPENDED', updated_at=? WHERE id=?",
            (iso_utc(), tenant_id))
        conn.execute(
            "UPDATE user_sessions SET revoked_at=? WHERE user_id IN "
            "(SELECT id FROM users WHERE tenant_id=?) AND revoked_at IS NULL",
            (iso_utc(), tenant_id))
    _audit(actor, tenant_id, "TENANT_SUSPEND", motivo=motivo)


def reactivar(tenant_id: int, motivo: str, actor) -> None:
    if not (motivo or "").strip():
        raise DomainError("El motivo es obligatorio para reactivar.")
    with transaction() as conn:
        conn.execute(
            "UPDATE tenants SET status='ACTIVE', updated_at=? WHERE id=?",
            (iso_utc(), tenant_id))
    _audit(actor, tenant_id, "TENANT_REACTIVATE", motivo=motivo)


def listar(busqueda: str | None = None, estado: str | None = None) -> list[dict]:
    sql = ("SELECT t.*, (SELECT count(*) FROM parking_sites s WHERE s.tenant_id = t.id) AS sedes, "
           "(SELECT count(*) FROM users u WHERE u.tenant_id = t.id AND u.is_active = 1) AS usuarios "
           "FROM tenants t WHERE 1=1")
    params: list = []
    if busqueda:
        sql += " AND (LOWER(t.name) LIKE ? OR t.nit LIKE ?)"
        params += [f"%{busqueda.lower()}%", f"%{busqueda}%"]
    if estado in ESTADOS:
        sql += " AND t.status = ?"
        params.append(estado)
    sql += " ORDER BY t.created_at DESC, t.id DESC"
    return query(sql, tuple(params))


def actualizar(tenant_id: int, campos: dict, actor: dict | None = None) -> dict:
    """PATCH del tenant (plan, límites, corte, nombre) — sólo plataforma."""
    actual = get_tenant(tenant_id)
    if not actual:
        raise NotFoundError()
    if "plan" in campos and campos["plan"] not in PLANES:
        raise DomainError("Plan desconocido.", {"plan": campos["plan"]})
    for limite in ("max_sites", "max_users"):
        if limite in campos and not 1 <= int(campos[limite]) <= 999:
            raise DomainError("Los límites deben estar entre 1 y 999.")
    if "billing_cutoff_day" in campos and not 1 <= int(campos["billing_cutoff_day"]) <= 28:
        raise DomainError("El día de corte debe ser 1–28.")
    if "name" in campos and not (campos["name"] or "").strip():
        raise DomainError("El nombre del cliente es obligatorio.")
    if "name" in campos and (otro := tenant_by_name(campos["name"])) and otro["id"] != tenant_id:
        raise ConflictError("Ya existe un cliente con ese nombre.", {"name": campos["name"]})
    if not campos:
        return actual
    antes = {k: actual[k] for k in campos}
    sets = ", ".join(f"{k} = ?" for k in campos) + ", updated_at = ?"
    with transaction() as conn:
        conn.execute(f"UPDATE tenants SET {sets} WHERE id = ?",
                     (*campos.values(), iso_utc(), tenant_id))
        conn.execute(
            "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
            "action, before_data, after_data) VALUES (?,?,?,?,?,?,?)",
            ((actor or {}).get("id"), tenant_id, "tenant", tenant_id,
             "TENANT_UPDATED",
             json.dumps(antes, ensure_ascii=False),
             json.dumps(campos, ensure_ascii=False)))
    return get_tenant(tenant_id)


def conteo_sedes(tenant_id: int) -> int:
    r = query_one("SELECT count(*) AS n FROM parking_sites WHERE tenant_id = ?", (tenant_id,))
    return int((r or {"n": 0})["n"])


def conteo_usuarios(tenant_id: int) -> int:
    r = query_one("SELECT count(*) AS n FROM users WHERE tenant_id = ? AND is_active = 1",
                  (tenant_id,))
    return int((r or {"n": 0})["n"])


def verificar_cuota_sede(tenant: dict) -> None:
    """docs del plan Fase 1: exceder max_sites → 409 limite_plan_alcanzado."""
    t = get_tenant(tenant["id"]) or tenant
    if int(conteo_sedes(t["id"])) >= int(t["max_sites"]):
        raise PlanLimitError(
            f"El plan {t['plan']} permite {t['max_sites']} sedes.", {"max_sites": t["max_sites"]})


def verificar_cuota_usuario(tenant: dict) -> None:
    t = get_tenant(tenant["id"]) or tenant
    if int(conteo_usuarios(t["id"])) >= int(t["max_users"]):
        raise PlanLimitError(
            f"El plan {t['plan']} permite {t['max_users']} usuarios.",
            {"max_users": t["max_users"]})


def _audit(actor: dict | None, tenant_id: int, accion: str, motivo: str = "",
           antes: dict | None = None, despues: dict | None = None) -> None:
    """Sin contraseñas ni tokens en before/after (docs/07 §7.7)."""
    u = actor or {}
    execute(
        "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, action, "
        "before_data, after_data) VALUES (?,?,?,?,?,?,?)",
        (u.get("id"), tenant_id, "tenant", tenant_id, accion,
         json.dumps(antes, ensure_ascii=False) if antes else None,
         json.dumps({"motivo": motivo, **(despues or {})}, ensure_ascii=False)))
