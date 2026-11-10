"""Configuración: tarifas, usuarios, sitio y plantilla (docs/04 §4.8, 05 §8)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_current_user, require_admin, require_superadmin
from ..domain import authentication as auth_mod
from ..domain import parking_operations as ops
from ..domain import site_settings as site_mod
from ..domain.errors import DomainError

router = APIRouter(tags=["configuracion"])


class TariffRequest(BaseModel):
    tipo_vehiculo: int
    nombre: str
    esquema: str
    monto: str
    gracia_minutos: int = 0
    fraccion_minutos: int | None = None


class UserRequest(BaseModel):
    usuario: str
    nombre_completo: str
    contraseña: str
    rol: str


class ResetRequest(BaseModel):
    nueva: str


class ActiveRequest(BaseModel):
    activo: bool


class SiteRequest(BaseModel):
    nombre: str | None = None
    nit: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    capacidad_total: int | None = None


class TemplateRequest(BaseModel):
    nombre_plantilla: str | None = None
    nombre_parqueadero: str | None = None
    nit: str | None = None
    direccion: str | None = None
    encabezado: str | None = None
    terminos: str | None = None
    pie: str | None = None
    mostrar_codigo_barras: bool | None = None
    mostrar_qr: bool | None = None


router = router  # noqa


@router.get("/api/tariffs")
def list_tariffs(user: dict = Depends(require_admin)):
    return ops.active_tariffs(ops.site(user["tenant_id"])["id"])


@router.post("/api/tariffs", status_code=201)
def create_tariff(body: TariffRequest, user: dict = Depends(require_admin)):
    ops.configure_tariff(ops.site(user["tenant_id"])["id"], body.tipo_vehiculo, body.nombre,
                         body.esquema, body.monto, body.gracia_minutos, body.fraccion_minutos,
                         user)
    return {"mensaje": "Tarifa creada (versionada)."}


@router.get("/api/users")
def list_users(user: dict = Depends(require_admin)):
    return auth_mod.list_users(user["tenant_id"])


@router.post("/api/users", status_code=201)
def create_user(body: UserRequest, user: dict = Depends(require_admin)):
    return auth_mod.create_user(body.usuario, body.contraseña, body.nombre_completo, body.rol, user)


@router.patch("/api/users/{user_id}/active")
def set_active(user_id: int, body: ActiveRequest, user: dict = Depends(require_admin)):
    auth_mod.set_user_active(user_id, body.activo, user)
    return {"mensaje": "Estado actualizado."}


@router.patch("/api/users/{user_id}/password")
def reset_password(user_id: int, body: ResetRequest, user: dict = Depends(require_admin)):
    auth_mod.change_user_password(user_id, body.nueva, user)
    return {"mensaje": "Contraseña restablecida; sesiones revocadas."}


@router.get("/api/site")
def get_site(user: dict = Depends(require_admin)):
    return site_mod.get_site(user)


@router.patch("/api/site")
def update_site(body: SiteRequest, user: dict = Depends(require_superadmin)):
    return site_mod.update_site(user, {k: v for k, v in body.model_dump().items() if v is not None})


@router.get("/api/receipt-template")
def get_template(user: dict = Depends(require_admin)):
    sede = ops.site(user["tenant_id"])
    return site_mod.get_receipt_template(sede["id"])


@router.patch("/api/receipt-template")
def update_template(body: TemplateRequest, user: dict = Depends(require_superadmin)):
    return site_mod.update_receipt_template(
        user, {k: v for k, v in body.model_dump().items() if v is not None})
