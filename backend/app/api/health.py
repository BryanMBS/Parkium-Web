"""Endpoint de salud (docs/04 §4.11, docs/05 §1 criterio 1.7)."""
from fastapi import APIRouter

from .. import db

router = APIRouter()


@router.get("/api/health")
def health():
    return db.health()
