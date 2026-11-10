"""Autenticación por cookie HttpOnly (docs/04 §4.2, 07 §7.3)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from .. import db
from ..config import settings
from ..deps import client_ip, get_current_user
from ..domain import authentication as auth_mod
from ..domain import time_utils
from ..domain.errors import ConflictError

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    usuario: str
    contraseña: str


class PasswordRequest(BaseModel):
    actual: str
    nueva: str


class FirstUserRequest(BaseModel):
    usuario: str
    nombre_completo: str
    contraseña: str


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        auth_mod.COOKIE_NAME, token,
        httponly=True, secure=settings.cookie_secure, samesite="lax",
        max_age=settings.duracion_sesion_horas * 3600, path="/",
    )


@router.post("/login")
def login(body: LoginRequest, resp: Response, request: Request):
    usuario, token = auth_mod.authenticate(body.usuario, body.contraseña, client_ip(request))
    expira = time_utils.utcnow().timestamp() + settings.duracion_sesion_horas * 3600
    _set_cookie(resp, token)
    from datetime import datetime, timezone
    return {
        "usuario": {
            "id": usuario["id"], "usuario": usuario["username"],
            "nombre": usuario["username"], "nombre_completo": usuario["full_name"],
            "rol": usuario["rol"], "etiqueta_rol": auth_mod.role_label(usuario["rol"]),
        },
        "expira_en": datetime.fromtimestamp(expira, tz=timezone.utc).isoformat(timespec="seconds"),
    }


@router.post("/logout", status_code=204)
def logout(request: Request):
    auth_mod.logout(request.cookies.get(auth_mod.COOKIE_NAME), client_ip(request))


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"], "usuario": user["username"], "nombre": user["username"],
        "nombre_completo": user["full_name"], "rol": user["rol"],
        "etiqueta_rol": auth_mod.role_label(user["rol"]),
    }


@router.post("/password")
def change_password(body: PasswordRequest, request: Request, user: dict = Depends(get_current_user)):
    auth_mod.change_own_password(user["id"], body.actual, body.nueva,
                                 token=request.cookies.get(auth_mod.COOKIE_NAME))
    return {"mensaje": "Contraseña actualizada. Se revocaron las demás sesiones."}


@router.post("/first-user")
def first_user(body: FirstUserRequest, request: Request, resp: Response):
    """Sólo válido si has_users() es falso; queda cerrado en cuanto exista uno."""
    if auth_mod.has_users():
        raise ConflictError("Ya existe un usuario: el acceso de primera ejecución quedó cerrado.")
    usuario = auth_mod.create_first_administrator(body.usuario, body.contraseña,
                                                  body.nombre_completo, client_ip(request))
    usuario2, token = auth_mod.authenticate(body.usuario, body.contraseña, client_ip(request))
    _set_cookie(resp, token)
    return {"usuario": {"id": usuario["id"], "nombre_completo": usuario["full_name"],
                        "rol": usuario["rol"]}}
