"""Mensualidades y convenios (docs/04 §4.6) — sólo ADMIN y SUPERADMIN."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import require_admin
from ..domain import subscriptions as subs_mod

router = APIRouter(prefix="/api", tags=["mensualidades"])


class CustomerRequest(BaseModel):
    nombre: str
    documento: dict | None = None
    telefono: str | None = None
    correo: str | None = None
    direccion: str | None = None
    placas: list[str] = []


class VehicleRequest(BaseModel):
    placa: str
    tipo_vehiculo: str = "CAR"


class SubscriptionRequest(BaseModel):
    cliente_id: int
    plan: str
    placas: list[str]
    inicio: str
    meses: int = 1
    valor: str
    horario: dict | None = None


class PayRequest(BaseModel):
    metodo: str = "CASH"
    monto: str
    efectivo_recibido: str | None = None
    referencia: str | None = None


class RenewRequest(BaseModel):
    metodo: str = "CASH"
    monto: str
    efectivo_recibido: str | None = None
    meses: int = 1
    referencia: str | None = None


class CancelRequest(BaseModel):
    motivo: str = ""


class AgreementRequest(BaseModel):
    cliente_id: int | None = None
    nombre: str
    tipo_descuento: str = "PERCENT"
    valor: str = "0"
    valido_desde: str
    valido_hasta: str | None = None


@router.get("/customers/plans")
def portfolio(q: str | None = None, estado: str | None = None, solo_saldo: bool = False,
              user: dict = Depends(require_admin)):
    return subs_mod.portfolio(user, q, estado, solo_saldo)


@router.post("/customers", status_code=201)
def create_customer(body: CustomerRequest, user: dict = Depends(require_admin)):
    return subs_mod.create_customer(user, body.model_dump())


@router.get("/customers/{customer_id}")
def customer(customer_id: int, user: dict = Depends(require_admin)):
    return subs_mod.customer_detail(customer_id, user["tenant_id"])


@router.get("/customers/{customer_id}/vehicles")
def customer_vehicles(customer_id: int, user: dict = Depends(require_admin)):
    return subs_mod.customer_vehicles(customer_id, user["tenant_id"])


@router.post("/customers/{customer_id}/vehicles", status_code=201)
def attach_vehicle(customer_id: int, body: VehicleRequest, user: dict = Depends(require_admin)):
    plate = subs_mod.attach_vehicle(user, customer_id, body.placa)
    return {"placa": plate}


@router.post("/subscriptions", status_code=201)
def create_subscription(body: SubscriptionRequest, user: dict = Depends(require_admin)):
    return subs_mod.create_subscription(user, body.model_dump())


@router.get("/subscriptions/alerts")
def alerts(dias_aviso: int = 7, user: dict = Depends(require_admin)):
    return subs_mod.subscription_alerts(user, dias_aviso)


@router.get("/subscriptions/{subscription_id}")
def subscription(subscription_id: int, user: dict = Depends(require_admin)):
    return subs_mod.get_subscription(subscription_id, user["tenant_id"])


@router.post("/subscriptions/{subscription_id}/pay")
def pay(subscription_id: int, body: PayRequest, user: dict = Depends(require_admin)):
    return subs_mod.pay_subscription(user, subscription_id, body.metodo, body.monto,
                                     body.efectivo_recibido, body.referencia)


@router.post("/subscriptions/{subscription_id}/renew")
def renew(subscription_id: int, body: RenewRequest, user: dict = Depends(require_admin)):
    return subs_mod.renew_subscription(user, subscription_id, body.metodo, body.monto,
                                       body.meses, body.efectivo_recibido, body.referencia)


@router.post("/subscriptions/{subscription_id}/cancel")
def cancel(subscription_id: int, body: CancelRequest, user: dict = Depends(require_admin)):
    return subs_mod.cancel_subscription(user, subscription_id, body.motivo)


@router.post("/agreements", status_code=201)
def agreement(body: AgreementRequest, user: dict = Depends(require_admin)):
    return subs_mod.create_agreement(user, body.model_dump())
