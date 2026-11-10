"""Dominio del módulo de plataforma (Fase 2) — espacio separado del operativo.

- Todo se ejecuta con actor PLATFORM_ADMIN (tenant_id NULL, guard en deps).
- Crear un tenant es UNA transacción (BEGIN IMMEDIATE): tenant + primera
  sede (opcional) + primer admin con contraseña temporal que obliga a cambio
  en el primer login (`users.must_change_password`).
- El andamiaje de cada sede nueva (contador de comprobantes, plantilla y
  tarifas HOUR estándar) replica el `seed.sql` del sistema mono-tenant.
- Ninguna acción borra datos; suspensión/reactivación exigen motivo.
"""
from __future__ import annotations

import json
import secrets

from ..db import transaction
from . import authentication as auth
from . import tenants as tdom
from .errors import ConflictError, DomainError, NotFoundError
from .time_utils import iso_utc

_TARIFAS_SEDE = ((1, "Hora carro", 5000.00), (2, "Hora moto", 3000.00),
                 (3, "Hora bicicleta", 2000.00))


def _andamio_sede(conn, tenant_id: int, site_id: int) -> None:
    """Lo mínimo para operar una sede: contador, plantilla y tarifas HOUR."""
    conn.execute("INSERT OR IGNORE INTO receipt_counters (site_id, next_number) "
                 "VALUES (?, 1)", (site_id,))
    conn.execute(
        "INSERT OR IGNORE INTO receipt_templates (site_id, tenant_id, template_name, "
        "parking_name, footer_text) VALUES (?, ?, 'Plantilla predeterminada', "
        "'PARKIUM', 'PARKIUM - Todos los derechos reservados.')", (site_id, tenant_id))
    for tipo_id, nombre, monto in _TARIFAS_SEDE:
        plan = conn.execute(
            "INSERT INTO tariff_plans (tenant_id, site_id, vehicle_type_id, name, "
            "billing_scheme, valid_from, is_active) VALUES (?,?,?,?,?,?,1)",
            (tenant_id, site_id, tipo_id, nombre, "HOUR", iso_utc())).lastrowid
        conn.execute("INSERT INTO tariff_rules (tariff_plan_id, sequence_no, "
                     "start_minute, end_minute, amount, grace_minutes) "
                     "VALUES (?,1,0,NULL,?,5)", (plan, monto))


def crear_tenant_completo(datos: dict, actor: dict, ip=None) -> dict:
    """UNA transacción: tenant + primera sede + primer admin (contraseña
    temporal que obliga a cambio en el primer login)."""
    sede_nombre = (datos.get("sede_nombre") or "").strip() or None
    password_temporal = secrets.token_urlsafe(9)     # ~12 chars; temporal
    with transaction() as conn:
        tenant_id = tdom.crear_tenant(
            datos.get("name"), datos.get("nit"), datos.get("plan") or "BASIC",
            datos.get("max_sites") if datos.get("max_sites") is not None else 1,
            datos.get("max_users") if datos.get("max_users") is not None else 5,
            datos.get("billing_cutoff_day") or 1, actor, conn=conn)
        if sede_nombre:
            cur = conn.execute(
                "INSERT INTO parking_sites (tenant_id, name, total_capacity) "
                "VALUES (?,?,?)", (tenant_id, sede_nombre,
                                   int(datos.get("sede_cupos") or 30)))
            site_id = int(cur.lastrowid or 0)
            _andamio_sede(conn, tenant_id, site_id)
        if datos.get("admin_username"):
            auth._validar_usuario(datos["admin_username"])
            auth._validar_contraseña(password_temporal)
            if auth_with_usuario_exists(datos["admin_username"]):
                raise ConflictError("Ya existe un usuario con ese nombre.",
                                    {"username": datos["admin_username"]})
            conn.execute(
                "INSERT INTO users (role_id, tenant_id, username, password_hash, "
                "full_name, must_change_password) VALUES (3,?,?,?,?,1)",
                (tenant_id, datos["admin_username"],
                 auth.hash_password(password_temporal),
                 datos.get("admin_nombre") or datos["admin_username"]))
            admin_id = int(conn.execute(
                "SELECT last_insert_rowid() AS id").fetchone()["id"])
        else:
            admin_id = None
        conn.execute(
            "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
            "action, before_data, after_data, ip_address) VALUES (?,?,?,?,?,?,?,?)",
            (actor["id"], tenant_id, "tenant", tenant_id, "TENANT_CREATED", None,
             json.dumps({"name": datos.get("name"), "nit": datos.get("nit"),
                         "plan": datos.get("plan"), "sede": sede_nombre,
                         "admin": datos.get("admin_username")}, ensure_ascii=False),
             ip))
    tenant = tdom.get_tenant(tenant_id)
    return {"tenant": tenant, "sede_id": sede_nombre and _id_primera_sede(tenant_id),
            "admin": auth.get_user(admin_id) if admin_id else None,
            "contrasena_temporal": password_temporal if admin_id else None}


def _id_primera_sede(tenant_id: int) -> int | None:
    from ..db import query_one
    r = query_one("SELECT id FROM parking_sites WHERE tenant_id = ? ORDER BY id LIMIT 1",
                  (tenant_id,))
    return r["id"] if r else None


def crear_sede(tenant_id: int, nombre: str, cupos: int, actor: dict, ip=None) -> dict:
    t = tdom.get_tenant(tenant_id)
    if not t:
        raise NotFoundError()
    tdom.verificar_cuota_sede(t)
    if not (nombre or "").strip():
        raise DomainError("El nombre de la sede es obligatorio.")
    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO parking_sites (tenant_id, name, total_capacity) VALUES (?,?,?)",
            (tenant_id, nombre.strip(), max(0, int(cupos))))
        site_id = int(cur.lastrowid or 0)
        _andamio_sede(conn, tenant_id, site_id)
        conn.execute(
            "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
            "action, after_data, ip_address) VALUES (?,?,?,?,?,?,?)",
            (actor["id"], tenant_id, "parking_site", site_id, "SITE_CREATED",
             json.dumps({"name": nombre.strip(), "tenant_id": tenant_id},
                        ensure_ascii=False), ip))
    from ..db import query_one
    return dict(query_one("SELECT * FROM parking_sites WHERE id = ?", (site_id,)))


def listar_sedes(tenant_id: int) -> list[dict]:
    from ..db import query
    return query("SELECT * FROM parking_sites WHERE tenant_id = ? ORDER BY id",
                 (tenant_id,))


def cargar_sede(tenant_id: int, site_id: int) -> dict:
    from ..db import query_one
    r = query_one("SELECT * FROM parking_sites WHERE id = ? AND tenant_id = ?",
                  (site_id, tenant_id))
    if not r:
        raise NotFoundError()
    return dict(r)


def actualizar_sede(tenant_id: int, site_id: int, campos: dict,
                    actor: dict, ip=None) -> dict:
    actual = cargar_sede(tenant_id, site_id)
    permitidos = {"name", "total_capacity", "tax_id", "address", "phone",
                  "is_active", "timezone"}
    cambios = {k: v for k, v in campos.items() if k in permitidos}
    if cambios.get("is_active"):
        raise DomainError("Activar/desactivar sedes se hace suspendiendo al tenant.")
    if not cambios:
        return actual
    sets = ", ".join(f"{k} = ?" for k in cambios)
    with transaction() as conn:
        conn.execute(f"UPDATE parking_sites SET {sets} WHERE id = ? AND tenant_id = ?",
                     (*cambios.values(), site_id, tenant_id))
        conn.execute(
            "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
            "action, before_data, after_data, ip_address) VALUES (?,?,?,?,?,?,?,?)",
            (actor["id"], tenant_id, "parking_site", site_id, "SITE_UPDATED",
             json.dumps({k: actual[k] for k in cambios}, ensure_ascii=False),
             json.dumps(cambios, ensure_ascii=False), ip))
    return cargar_sede(tenant_id, site_id)


def listar_admins(tenant_id: int) -> list[dict]:
    from ..db import query
    return query(
        "SELECT u.id, u.username, u.full_name, u.is_active, u.last_login_at, "
        "u.must_change_password, r.code AS rol "
        "FROM users u JOIN roles r ON r.id = u.role_id "
        "WHERE u.tenant_id = ? AND r.code IN ('ADMIN','SUPERADMIN') ORDER BY u.id",
        (tenant_id,))


def crear_admin(tenant_id: int, datos: dict, actor: dict, ip=None) -> dict:
    t = tdom.get_tenant(tenant_id)
    if not t:
        raise NotFoundError()
    tdom.verificar_cuota_usuario(t)
    usuario = (datos.get("username") or "").strip()
    auth._validar_usuario(usuario)
    contraseña_semi = secrets.token_urlsafe(9)
    auth._validar_contraseña(contraseña_semi)
    role_id = 3 if datos.get("rol") == "SUPERADMIN" else 1   # sembrados: 1=ADMIN, 3=SUPERADMIN
    if auth_with_usuario_exists(usuario):
        raise ConflictError("Ya existe un usuario con ese nombre.", {"username": usuario})
    with transaction() as conn:
        conn.execute(
            "INSERT INTO users (role_id, tenant_id, username, password_hash, "
            "full_name, must_change_password) VALUES (?,?,?,?,?,1)",
            (role_id, tenant_id, usuario, auth.hash_password(contraseña_semi),
             datos.get("nombre") or usuario))
        uid = int(conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"])
    _audit_platform(actor, tenant_id, "TENANT_ADMIN_CREATED", uid,
                    {"username": usuario})
    return {"usuario": auth.get_user(uid), "contrasena_temporal": contraseña_semi}


def auth_with_usuario_exists(usuario: str) -> bool:
    from ..db import query_one
    return bool(query_one("SELECT id FROM users WHERE username = ?", (usuario,)))


def fijar_contraseña_admin(tenant_id: int, user_id: int, nueva: str,
                           actor: dict, ip=None) -> None:
    """Igual que el «Fijar» de Configuración > Usuarios, pero desde plataforma."""
    objetivo = auth.get_user(user_id)
    if not objetivo or objetivo not in listar_admins(tenant_id):
        raise NotFoundError()
    auth._validar_contraseña(nueva)
    with transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ?, must_change_password = 0, "
                     "updated_at = ? WHERE id = ?",
                     (auth.hash_password(nueva), iso_utc(), user_id))
        conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? "
                     "AND revoked_at IS NULL", (iso_utc(), user_id))
    _audit_platform(actor, tenant_id, "TENANT_ADMIN_PASSWORD_SET", user_id,
                    {"username": objetivo["username"]})


def _audit_platform(actor: dict, tenant_id: int, accion: str, entidad_id: int,
                    despues: dict) -> None:
    from ..db import execute
    execute(
        "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
        "action, after_data) VALUES (?,?,?,?,?,?)",
        (actor["id"], tenant_id, "platform", entidad_id, accion,
         json.dumps(despues, ensure_ascii=False)))


def resumen() -> dict:
    from ..db import query_one
    return {
        "clientes": query_one("SELECT count(*) AS n FROM tenants")["n"],
        "activos": query_one("SELECT count(*) AS n FROM tenants WHERE status='ACTIVE'")["n"],
        "suspendidos": query_one(
            "SELECT count(*) AS n FROM tenants WHERE status='SUSPENDED'")["n"],
        "sedes": query_one("SELECT count(*) AS n FROM parking_sites")["n"],
        "usuarios": query_one(
            "SELECT count(*) AS n FROM users WHERE tenant_id IS NOT NULL")["n"],
    }


def auditar(pagina: int = 1, por_pagina: int = 25, desde=None, hasta=None,
            accion=None, tenant_id=None) -> dict:
    from ..db import query
    sql = ("SELECT a.id, a.action, a.entity_type, a.entity_id, a.tenant_id, "
           "t.name AS tenant, a.occurred_at, a.ip_address, u.username AS actor, "
           "a.before_data, a.after_data FROM audit_logs a "
           "LEFT JOIN users u ON u.id = a.user_id "
           "LEFT JOIN tenants t ON t.id = a.tenant_id WHERE 1=1")
    params: list = []
    if desde:
        sql += " AND a.occurred_at >= ?"; params.append(f"{desde}T00:00:00")
    if hasta:
        sql += " AND a.occurred_at <= ?"; params.append(f"{hasta}T23:59:59")
    if accion:
        sql += " AND a.action LIKE ?"; params.append(f"%{accion}%")
    if tenant_id:
        sql += " AND a.tenant_id = ?"; params.append(tenant_id)
    sql += " ORDER BY a.occurred_at DESC, a.id DESC LIMIT ? OFFSET ?"
    params += [por_pagina, max(0, (pagina - 1)) * por_pagina]
    return {"pagina": pagina, "por_pagina": por_pagina,
            "eventos": query(sql, tuple(params))}
