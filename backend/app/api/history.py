"""Histórico y ocupación por hora (docs/04 §4.5) — sólo ADMIN y SUPERADMIN."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..deps import require_admin
from ..domain import history as hist_mod

router = APIRouter(prefix="/api", tags=["historico"])


@router.get("/history")
def history(placa: str | None = None, desde: str | None = None, hasta: str | None = None,
            estado: str | None = None, tipo_vehiculo: str | None = None,
            limite: int = 500, user: dict = Depends(require_admin)):
    return hist_mod.search_history(user, placa, desde, hasta, estado, tipo_vehiculo, limite)


@router.get("/occupancy/hourly")
def occupancy_hourly(fecha: str, user: dict = Depends(require_admin)):
    return hist_mod.occupancy_by_hour(user, fecha)


@router.get("/occupancy/detail")
def occupancy_detail(fecha: str, hora: int, user: dict = Depends(require_admin)):
    return hist_mod.occupancy_detail(user, fecha, hora)
