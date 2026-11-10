"""Dependencias de la API: sesión por cookie y autorización por rol (docs/07 §7.3)."""
from __future__ import annotations

from fastapi import Depends, Request

from .domain import authentication as auth
from .domain import tenants
from .domain.errors import AuthorizationError, NotAuthenticatedError
from .db import query_one


def _token(request: Request) -> str | None:
    return request.cookies.get(auth.COOKIE_NAME)


def get_current_user(request: Request) -> dict:
    token = _token(request)
    if not token:
        raise NotAuthenticatedError()
    session = query_one(
        "SELECT * FROM user_sessions WHERE token_hash = ?", (auth._token_hash(token),))
    if not session or session["revoked_at"]:
        raise NotAuthenticatedError()
    expira = session["expires_at"]
    # todos los tiempos se validan en el servidor, nunca en el cliente
    user = auth.validate_session(token)
    return user if "token" not in user else user


def require_role(*roles):
    def _dep(user: dict = Depends(get_current_user)) -> dict:
        auth.require_role(user, roles)
        return user
    return _dep


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    auth.require_admin(user)
    return user


def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    auth.require_superadmin(user)
    return user


def require_platform(user: dict = Depends(get_current_user)) -> dict:
    """Fase 2: las rutas /api/platform/* exigen PLATFORM_ADMIN (tenant NULL)."""
    auth.require_platform(user)
    return user


def get_tenant(user: dict = Depends(get_current_user)) -> dict:
    """Fase 1: el tenant del usuario SIEMPRE sale de la sesión (servidor);
    nunca del body ni de la URL en rutas operativas."""
    if not user.get("tenant_id"):
        # PLATFORM_ADMIN u operador huérfano: fuera de las rutas operativas
        raise AuthorizationError("La petición requiere una sesión de tenant.")
    tenant = tenants.get_tenant(user["tenant_id"])
    if not tenant or tenant["status"] != "ACTIVE":
        raise AuthorizationError("Cuenta suspendida, contacta a soporte")
    return tenant


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For")
    return (forwarded.split(",")[0].strip() if forwarded else None) or request.client.host if request.client else forwarded
