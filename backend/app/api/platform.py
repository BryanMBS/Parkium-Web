"""API del módulo de plataforma (Fase 2, docs del plan) — sólo PLATFORM_ADMIN.

Todo endpoint exige la dependencia `require_platform`; un usuario de tenant
(incluido SUPERADMIN de tenant) recibe 403. Los importes/fechas siguen las
convenciones de docs/04; los errores usan el contrato { codigo, mensaje, detalle }.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from ..deps import client_ip, require_platform
from ..domain import platform as plat
from ..domain import tenants as tdom
from ..domain.errors import NotFoundError

router = APIRouter(prefix="/api/platform", tags=["plataforma"])


class TenantCreate(BaseModel):
    name: str
    nit: str
    plan: str = "BASIC"
    max_sites: int = 1
    max_users: int = 5
    billing_cutoff_day: int = 1
    sede_nombre: str | None = None
    sede_cupos: int | None = None
    admin_username: str | None = None
    admin_nombre: str | None = None


class TenantPatch(BaseModel):
    name: str | None = None
    plan: str | None = None
    max_sites: int | None = None
    max_users: int | None = None
    billing_cutoff_day: int | None = None


class Motivo(BaseModel):
    motivo: str


class SedeCreate(BaseModel):
    name: str
    total_capacity: int = 30


class SedePatch(BaseModel):
    name: str | None = None
    total_capacity: int | None = None
    tax_id: str | None = None
    address: str | None = None
    phone: str | None = None
    is_active: int | None = None


class AdminCreate(BaseModel):
    username: str
    nombre: str | None = None
    rol: str = "ADMIN"


class AdminPassword(BaseModel):
    nueva: str


@router.get("/summary")
def summary(user: dict = Depends(require_platform)):
    return plat.resumen()


@router.get("/tenants")
def listar(q: str | None = None, estado: str | None = None,
           user: dict = Depends(require_platform)):
    return tdom.listar(q, estado)


@router.post("/tenants", status_code=201)
def crear(body: TenantCreate, request: Request,
          user: dict = Depends(require_platform)):
    return plat.crear_tenant_completo(body.model_dump(), user, client_ip(request))


def _tenant_o_404(tenant_id: int) -> dict:
    t = tdom.get_tenant(tenant_id)
    if not t:
        raise NotFoundError()
    return t


@router.get("/tenants/{tenant_id}")
def detalle(tenant_id: int, user: dict = Depends(require_platform)):
    return _tenant_o_404(tenant_id)


@router.patch("/tenants/{tenant_id}")
def patchear(tenant_id: int, body: TenantPatch, request: Request,
             user: dict = Depends(require_platform)):
    _tenant_o_404(tenant_id)
    campos = {k: v for k, v in body.model_dump().items() if v is not None}
    return tdom.actualizar(tenant_id, campos, user)


@router.post("/tenants/{tenant_id}/suspend")
def suspender(tenant_id: int, body: Motivo, request: Request,
              user: dict = Depends(require_platform)):
    _tenant_o_404(tenant_id)
    tdom.suspender(tenant_id, body.motivo, user)   # revoca las sesiones del tenant
    return {"estado": "SUSPENDED"}


@router.post("/tenants/{tenant_id}/reactivate")
def reactivar(tenant_id: int, body: Motivo, request: Request,
              user: dict = Depends(require_platform)):
    _tenant_o_404(tenant_id)
    tdom.reactivar(tenant_id, body.motivo, user)
    return {"estado": "ACTIVE"}


@router.get("/tenants/{tenant_id}/sites")
def sedes(tenant_id: int, user: dict = Depends(require_platform)):
    _tenant_o_404(tenant_id)
    return plat.listar_sedes(tenant_id)


@router.post("/tenants/{tenant_id}/sites", status_code=201)
def nueva_sede(tenant_id: int, body: SedeCreate, request: Request,
               user: dict = Depends(require_platform)):
    return plat.crear_sede(tenant_id, body.name, body.total_capacity,
                           user, client_ip(request))


@router.patch("/tenants/{tenant_id}/sites/{site_id}")
def patch_sede(tenant_id: int, site_id: int, body: SedePatch, request: Request,
               user: dict = Depends(require_platform)):
    return plat.actualizar_sede(tenant_id, site_id,
                                {k: v for k, v in body.model_dump().items() if v is not None},
                                user, client_ip(request))


@router.get("/tenants/{tenant_id}/admins")
def admins(tenant_id: int, user: dict = Depends(require_platform)):
    _tenant_o_404(tenant_id)
    return plat.listar_admins(tenant_id)


@router.post("/tenants/{tenant_id}/admins", status_code=201)
def nuevo_admin(tenant_id: int, body: AdminCreate, request: Request,
                user: dict = Depends(require_platform)):
    return plat.crear_admin(tenant_id, body.model_dump(), user, client_ip(request))


@router.post("/tenants/{tenant_id}/admins/{user_id}/password")
def reset_password(tenant_id: int, user_id: int, body: AdminPassword,
                   request: Request, user: dict = Depends(require_platform)):
    plat.fijar_contraseña_admin(tenant_id, user_id, body.nueva, user, client_ip(request))
    return {"estado": "fijada"}


@router.get("/audit")
def auditoria(pagina: int = 1, por_pagina: int = 25, desde: str | None = None,
              hasta: str | None = None, accion: str | None = None,
              tenant_id: int | None = None, user: dict = Depends(require_platform)):
    return plat.auditar(pagina, por_pagina, desde, hasta, accion, tenant_id)
