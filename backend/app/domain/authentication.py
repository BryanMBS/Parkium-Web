"""Autenticación y sesiones — replicación fiel de app/services/authentication.py.

docs/07 §7.2/7.3: scrypt N=16384, r=8, p=1, contraseñas 10–256,
usuario ^[A-Za-z0-9._-]{3,60}$, sesión 12 h, token sólo como SHA-256,
`_ROLE_IMPLICITS` no es una jerarquía.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import timedelta
from typing import Iterable

from ..config import (
    DEFAULT_SITE_ID, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH,
    SCRYPT_N, SCRYPT_P, SCRYPT_R, SCRYPT_SAFE, SESSION_DURATION,
)
from ..db import execute, query, query_one, transaction
from .errors import (
    AuthorizationError, ConflictError, CredentialsError, DomainError,
    NotAuthenticatedError, NotFoundError,
)
from . import time_utils

ROLE_SUPERADMIN = "SUPERADMIN"
ROLE_ADMIN = "ADMIN"
ROLE_OPERATOR = "OPERATOR"
ROLE_PLATFORM = "PLATFORM_ADMIN"   # Fase 2: espacio separado, tenant_id NULL
ROLES = (ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_OPERATOR)

# docs/07 §7.1: el super administrador satisface cualquier requisito;
# ADMIN sólo los que aceptan ADMIN. No implementar jerarquías extra.
_ROLE_IMPLICITS = {
    ROLE_SUPERADMIN: frozenset(ROLES),
    ROLE_ADMIN: frozenset({ROLE_ADMIN}),
    ROLE_OPERATOR: frozenset({ROLE_OPERATOR}),
}

ROLE_LABELS = {
    ROLE_SUPERADMIN: "Super administrador",
    ROLE_ADMIN: "Administrador",
    ROLE_OPERATOR: "Operador",
}

_USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,60}$")
_HASH_RE = re.compile(r"^scrypt\$([^$]+)\$([^$]+)\$([^$]+)\$([^$]+)\$([^$]+)$")
COOKIE_NAME = "parkium_sesion"


def hash_password(contraseña: str) -> str:
    _validar_contraseña(contraseña)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(contraseña.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(contraseña: str, stored: str) -> bool:
    m = _HASH_RE.match(stored or "")
    if not m:
        return False
    n, r, p = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if (n, r, p) not in SCRYPT_SAFE:
        # docs/07 §7.2: un perfil manipulado en la base se rechaza
        return False
    try:
        salt = bytes.fromhex(m.group(4))
        esperado = bytes.fromhex(m.group(5))
        digest = hashlib.scrypt(contraseña.encode("utf-8"), salt=salt, n=n, r=r, p=p)
        return secrets.compare_digest(digest, esperado)
    except (ValueError, OSError):
        return False


def _validar_contraseña(contraseña: str) -> None:
    n = len(contraseña or "")
    if n < PASSWORD_MIN_LENGTH or n > PASSWORD_MAX_LENGTH:
        raise DomainError(f"La contraseña debe tener entre {PASSWORD_MIN_LENGTH} y {PASSWORD_MAX_LENGTH} caracteres.")


def _validar_usuario(usuario: str) -> None:
    if not _USERNAME_PATTERN.match(usuario or ""):
        raise DomainError("El usuario debe tener entre 3 y 60 caracteres alfanuméricos, punto, guión o subrayado.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def has_users() -> bool:
    row = query_one("SELECT count(*) AS n FROM users")
    return bool(row and row["n"])


def get_role(role_id: int) -> dict | None:
    return query_one("SELECT id, code, name, description FROM roles WHERE id = ?", (role_id,))


def role_label(rol: str) -> str:
    return ROLE_LABELS.get(rol, rol)


def _audit(conn, user_id, entity_type, entity_id, action, before, after, ip=None):
    import json
    conn.execute(
        "INSERT INTO audit_logs (user_id, entity_type, entity_id, action, before_data, after_data, occurred_at, ip_address) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (user_id, entity_type, entity_id, action,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False) if after is not None else None,
         time_utils.iso_utc(), ip),
    )


def audit(user_id, entity_type, entity_id, action, before=None, after=None, ip=None):
    from ..db import _connect  # noqa
    with transaction() as conn:
        _audit(conn, user_id, entity_type, entity_id, action, before, after, ip)


def authenticate(usuario: str, contraseña: str, ip: str | None = None) -> tuple[dict, str]:
    """Devuelve (usuario, token). audits LOGIN_SUCCESS/LOGIN_FAILED."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT u.*, r.code AS rol FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE u.username = ?", (usuario,)).fetchone()
        data = dict(row) if row else None
        if not data or not verify_password(contraseña, data["password_hash"]):
            _audit(conn, data["id"] if data else None, "AUTH", data["id"] if data else None,
                   "LOGIN_FAILED", None, {"usuario": usuario}, ip)
            raise CredentialsError()
        if not data["is_active"]:
            raise CredentialsError("El usuario está inactivo.")
        # Multi-tenant: un tenant SUSPENDED no puede iniciar sesión (Fase 1).
        if data["tenant_id"]:
            t = conn.execute("SELECT status FROM tenants WHERE id = ?",
                             (data["tenant_id"],)).fetchone()
            if not t or t["status"] == "SUSPENDED":
                _audit(conn, data["id"], "AUTH", data["id"], "LOGIN_BLOCKED_SUSPENDED",
                       None, {"usuario": usuario, "tenant_id": data["tenant_id"]}, ip)
                raise AuthorizationError("Cuenta suspendida, contacta a soporte")
        token = secrets.token_urlsafe(32)
        expiry = time_utils.utcnow() + timedelta(seconds=SESSION_DURATION)
        conn.execute(
            "INSERT INTO user_sessions (user_id, token_hash, created_at, expires_at) VALUES (?,?,?,?)",
            (data["id"], _token_hash(token), time_utils.iso_utc(), time_utils.iso_utc(expiry)))
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (time_utils.iso_utc(), data["id"]))
        _audit(conn, data["id"], "AUTH", data["id"], "LOGIN_SUCCESS", None, None, ip)
    return data, token


def validate_session(token: str | None) -> dict:
    if not token:
        raise NotAuthenticatedError()
    session = query_one(
        "SELECT * FROM user_sessions WHERE token_hash = ?", (_token_hash(token),))
    if not session or session["revoked_at"]:
        raise NotAuthenticatedError()
    expires = time_utils.parse_iso(session["expires_at"])
    if expires is None or expires <= time_utils.utcnow():
        raise NotAuthenticatedError()
    usuario = query_one(
        "SELECT u.*, r.code AS rol FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?",
        (session["user_id"],))
    if not usuario or not usuario["is_active"]:
        raise NotAuthenticatedError()
    # Multi-tenant: la suspensión del tenant invalida la sesión en la
    # SIGUIENTE petición (Fase 1), sin revocar filas a mano.
    if usuario["tenant_id"]:
        t = query_one("SELECT status FROM tenants WHERE id = ?", (usuario["tenant_id"],))
        if not t or t["status"] == "SUSPENDED":
            raise AuthorizationError("Cuenta suspendida, contacta a soporte")
    return usuario


def logout(token: str | None, ip: str | None = None) -> None:
    if not token or not _find_valid(token):
        return
    with transaction() as conn:
        conn.execute(
            "UPDATE user_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (time_utils.iso_utc(), _token_hash(token)))
        session = conn.execute(
            "SELECT user_id FROM user_sessions WHERE token_hash = ?", (_token_hash(token),)).fetchone()
        if session:
            _audit(conn, session["user_id"], "AUTH", session["user_id"], "LOGOUT", None, None, ip)


def _find_valid(token: str) -> bool:
    try:
        validate_session(token)
        return True
    except NotAuthenticatedError:
        return False


def cleanup_expired_sessions() -> int:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM user_sessions WHERE expires_at < ? OR revoked_at IS NOT NULL",
            (time_utils.iso_utc(),))
        return cur.rowcount


def require_role(user: dict, roles: Iterable[str], mensaje: str | None = None) -> None:
    """Port literal de require_role (docs/07 §7.1)."""
    permitidos = _ROLE_IMPLICITS.get(user["rol"], frozenset())
    if user["rol"] not in permitidos or not (set(roles) & set(permitidos)):
        raise AuthorizationError(mensaje)


def require_admin(user: dict) -> None:
    require_role(user, [ROLE_ADMIN, ROLE_SUPERADMIN])


def require_superadmin(user: dict) -> None:
    require_role(user, [ROLE_SUPERADMIN], "Sólo el super administrador puede hacer esto.")


def create_first_administrator(usuario, contraseña, nombre_completo, ip=None) -> dict:
    if has_users():
        raise ConflictError("Ya existe un usuario: el acceso de primera ejecución quedó cerrado.")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO users (role_id, username, password_hash, full_name) VALUES (?,?,?,?)",
            (3, usuario, hash_password(contraseña), nombre_completo))
        new_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        _audit(conn, new_id, "user", new_id, "USER_CREATED_INITIAL_SUPERADMIN",
               None, {"usuario": usuario, "rol": ROLE_SUPERADMIN}, ip)
    return get_user(new_id)


def create_user(usuario, contraseña, nombre_completo, rol, creador: dict, ip=None) -> dict:
    """docs/07 §7.4: ADMIN puede crear OPERATOR/ADMIN; SUPERADMIN crea cualquiera."""
    require_admin(creador)
    _validar_usuario(usuario)
    if rol not in ROLES:
        raise DomainError("Rol inválido.")
    if rol == ROLE_SUPERADMIN:
        require_superadmin(creador)
    elif rol not in (ROLE_ADMIN, ROLE_OPERATOR):
        raise DomainError("Rol inválido.")
    _validar_contraseña(contraseña)
    if query_one("SELECT id FROM users WHERE username = ?", (usuario,)):
        raise ConflictError("Ya existe un usuario con ese nombre.")
    role_row = query_one("SELECT id FROM roles WHERE code = ?", (rol,))
    with transaction() as conn:
        conn.execute(
            "INSERT INTO users (role_id, tenant_id, username, password_hash, full_name) "
            "VALUES (?,?,?,?,?)",
            (role_row["id"], creador.get("tenant_id"), usuario,
             hash_password(contraseña), nombre_completo))
        new_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        _audit(conn, creador["id"], "user", new_id, "USER_CREATED",
               None, {"usuario": usuario, "rol": rol}, ip)
    return get_user(new_id)


def require_platform(user: dict) -> None:
    """Fase 2: un usuario de tenant NO es PLATFORM_ADMIN y vive en otro espacio."""
    if user.get("rol") != ROLE_PLATFORM or user.get("tenant_id") is not None:
        raise AuthorizationError("Requiere el rol de administrador de plataforma.")


def list_users(tenant_id: int | None = None) -> list[dict]:
    """Con tenant_id lista sólo los usuarios del tenant (+ PLATAFORMA excluida).
    Alias en español para la UI (fix UX-D-CONTRATO)."""
    if tenant_id is None:
        return query(
            "SELECT u.id, u.username, u.username AS usuario, u.full_name, "
            "u.full_name AS nombre_completo, u.is_active, u.last_login_at, r.code AS rol "
            "FROM users u JOIN roles r ON r.id = u.role_id ORDER BY u.id")
    return query(
        "SELECT u.id, u.username, u.username AS usuario, u.full_name, "
        "u.full_name AS nombre_completo, u.is_active, u.last_login_at, r.code AS rol "
        "FROM users u JOIN roles r ON r.id = u.role_id WHERE u.tenant_id = ? ORDER BY u.id",
        (tenant_id,))


def get_user(user_id: int) -> dict | None:
    return query_one(
        "SELECT u.id, u.username, u.full_name, u.is_active, u.last_login_at, r.code AS rol "
        "FROM users u JOIN roles r ON r.id = u.role_id WHERE u.id = ?", (user_id,))


def set_user_active(user_id: int, activo: bool, actor: dict, ip=None) -> None:
    require_admin(actor)
    if user_id == actor["id"] and not activo:
        raise DomainError("No puede desactivar su propia cuenta.")
    objetivo = get_user(user_id)
    if not objetivo:
        raise NotFoundError()
    # aislamiento: un admin de tenant sólo toca usuarios de SU tenant
    if actor.get("tenant_id") and objetivo.get("tenant_id") != actor["tenant_id"]:
        raise NotFoundError()
    if objetivo["rol"] == ROLE_SUPERADMIN and actor["rol"] != ROLE_SUPERADMIN:
        raise AuthorizationError("No puede modificar la cuenta de un super administrador.")
    with transaction() as conn:
        new_state = 1 if activo else 0
        conn.execute("UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
                     (new_state, time_utils.iso_utc(), user_id))
        if not activo:
            conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                         (time_utils.iso_utc(), user_id))
        _audit(conn, actor["id"], "user", user_id, "USER_ACTIVATION_CHANGED",
               {"is_active": objetivo["is_active"]}, {"is_active": new_state}, ip)


def change_own_password(user_id: int, actual: str, nueva: str, token: str | None = None, ip=None) -> None:
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if not user or not verify_password(actual, user["password_hash"]):
        raise CredentialsError("La contraseña actual no coincide.")
    _validar_contraseña(nueva)
    with transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                     (hash_password(nueva), time_utils.iso_utc(), user_id))
        # docs/07 §7.6: revoca todas las sesiones salvo la actual
        if token:
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL "
                "AND token_hash <> ?",
                (time_utils.iso_utc(), user_id, _token_hash(token)))
        _audit(conn, user_id, "user", user_id, "PASSWORD_CHANGED", None, None, ip)


def change_user_password(user_id: int, nueva: str, actor: dict, ip=None) -> None:
    """Un admin cambia la de un normal; NUNCA la del super admin (docs/07 §7.4)."""
    require_admin(actor)
    objetivo = get_user(user_id)
    if not objetivo:
        raise NotFoundError()
    # aislamiento: sólo usuarios del mismo tenant del actor
    if actor.get("tenant_id") and objetivo.get("tenant_id") != actor["tenant_id"]:
        raise NotFoundError()
    if objetivo["rol"] == ROLE_SUPERADMIN:
        require_superadmin(actor, "No puede cambiar la contraseña de un super administrador.")
    _validar_contraseña(nueva)
    with transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                     (hash_password(nueva), time_utils.iso_utc(), user_id))
        conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                     (time_utils.iso_utc(), user_id))
        _audit(conn, actor["id"], "user", user_id, "PASSWORD_RESET_BY_ADMIN", None, None, ip)


def reset_administrator_password(usuario: str, nueva: str) -> None:
    """docs/12 §2: NO separado por HTTP. Sólo para scripts de consola del servidor."""
    user = query_one(
        "SELECT u.*, r.code AS rol FROM users u JOIN roles r ON r.id = u.role_id WHERE u.username = ?",
        (usuario,))
    if not user or user["rol"] not in (ROLE_ADMIN, ROLE_SUPERADMIN):
        raise NotFoundError("No existe la cuenta administrativa indicada.")
    _validar_contraseña(nueva)
    with transaction() as conn:
        conn.execute("UPDATE users SET password_hash = ?, is_active = 1, updated_at = ? WHERE id = ?",
                     (hash_password(nueva), time_utils.iso_utc(), user["id"]))
        conn.execute("UPDATE user_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                     (time_utils.iso_utc(), user["id"]))
        _audit(conn, None, "user", user["id"], "PASSWORD_RESET_LOCAL", None, None, None)
