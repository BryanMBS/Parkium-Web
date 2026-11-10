"""Operación: entradas, cotización, cobro, anulaciones y ocupación (docs/04 §4.3)."""
from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from ..deps import get_current_user, get_tenant
from ..domain import parking_operations as ops
from ..domain import reports as reports_mod
from ..domain.errors import NotFoundError

router = APIRouter(prefix="/api", tags=["operacion"])


class EntryRequest(BaseModel):
    placa: str
    tipo_vehiculo: str = "CAR"


class CheckoutRequest(BaseModel):
    placa: str
    metodo: str = "CASH"
    monto: str | None = None
    efectivo_recibido: str | None = None
    referencia: str | None = None


class VoidRequest(BaseModel):
    motivo: str = ""


@router.post("/stays", status_code=201)
def register_entry(body: EntryRequest, user: dict = Depends(get_current_user),
                   tenant: dict = Depends(get_tenant)):
    # UX-S007, decisión: NO se replica el Header Idempotency-Key de /checkout.
    # La idempotencia aquí es estructural: una placa no puede tener dos
    # estadías activas (ops.register_entry → ConflictError), así que un doble
    # envío o reintento nunca duplica la entrada. Una clave explícita exigiría
    # una columna nueva en parking_stays (migración sobre la BD operativa) sin
    # beneficio adicional. El frontend además deshabilita el botón mientras
    # envía («Registrando…»).
    return ops.register_entry(user, body.placa, body.tipo_vehiculo)


@router.get("/stays/active")
def active_stay(placa: str, user: dict = Depends(get_current_user),
                tenant: dict = Depends(get_tenant)):
    stay = ops.find_active_stay(ops.normalise_plate(placa), user["tenant_id"])
    if not stay:
        raise NotFoundError()
    site_row = ops.site(user["tenant_id"])
    from ..domain import time_utils
    vehicle = ops.find_vehicle_by_id(stay["vehicle_id"])
    entrada = time_utils.parse_iso(stay["entry_at"])
    return {"estadia_id": stay["id"], "placa": vehicle["plate"] if vehicle else None,
            "ingreso_local": time_utils.local_str(entrada, site_row), "estado": stay["status"]}


@router.get("/stays/{placa}/quote")
def quote(placa: str, user: dict = Depends(get_current_user),
          tenant: dict = Depends(get_tenant)):
    return ops.quote_exit(user, placa)


@router.post("/checkout")
def checkout(body: CheckoutRequest, user: dict = Depends(get_current_user),
             tenant: dict = Depends(get_tenant),
             idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")):
    key = idempotency_key or str(uuid4())
    return ops.collect_payment(user, body.placa, body.metodo, body.monto or "0",
                               body.efectivo_recibido, body.referencia, key)


@router.post("/payments/{payment_id}/void")
def void(payment_id: int, body: VoidRequest, user: dict = Depends(get_current_user),
         tenant: dict = Depends(get_tenant)):
    return ops.void_payment(user, payment_id, body.motivo)


@router.get("/occupancy")
def occupancy(user: dict = Depends(get_current_user),
              tenant: dict = Depends(get_tenant)):
    return ops.occupancy(tenant=user["tenant_id"])


@router.get("/dashboard")
def dashboard(user: dict = Depends(get_current_user),
              tenant: dict = Depends(get_tenant)):
    return reports_mod.dashboard_summary(user)
