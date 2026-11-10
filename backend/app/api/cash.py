"""Caja por turno (docs/04 §4.7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..deps import get_current_user
from ..domain import cash as cash_mod

router = APIRouter(prefix="/api/cash", tags=["caja"])


class OpenRequest(BaseModel):
    monto_inicial: str = "0"


class CloseRequest(BaseModel):
    monto_contado: str


@router.post("/shifts", status_code=201)
def open_shift(body: OpenRequest, user: dict = Depends(get_current_user)):
    return cash_mod.open_cash_shift(user, body.monto_inicial)


@router.get("/shifts")
def list_shifts(abiertos: bool = True, user: dict = Depends(get_current_user)):
    return cash_mod.list_open_shifts(user)


@router.get("/shifts/{shift_id}/expected")
def expected(shift_id: int, user: dict = Depends(get_current_user)):
    return cash_mod.expected_cash(user, shift_id)


@router.post("/shifts/{shift_id}/close")
def close(shift_id: int, body: CloseRequest, user: dict = Depends(get_current_user)):
    return cash_mod.close_cash_shift(user, shift_id, body.monto_contado)
