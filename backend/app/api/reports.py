"""Reportes y exportaciones (docs/04 §4.9) — sólo super administrador."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from ..deps import get_current_user, require_superadmin
from ..domain import reports as rep
from ..domain import exporters

router = APIRouter(prefix="/api", tags=["reportes"])


@router.get("/reports/summary")
def summary(desde: str | None = None, hasta: str | None = None,
            user: dict = Depends(require_superadmin)):
    return rep.operation_summary(user, desde, hasta)


@router.get("/reports/summary.csv")
def summary_csv(desde: str | None = None, hasta: str | None = None,
                user: dict = Depends(require_superadmin)):
    csv_page = rep.export_csv(user, desde, hasta)
    return Response(content=csv_page.encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=parkium_resumen.csv"})


@router.get("/reports/summary.json")
def summary_json(desde: str | None = None, hasta: str | None = None,
                 user: dict = Depends(require_superadmin)):
    # importes como texto; nunca números de JavaScript (docs/04 §4.9)
    payload = rep.export_json(user, desde, hasta)
    return Response(content=payload, media_type="application/json")


# ── exportaciones restantes de docs/04 §4.9 (XLSX y PDF) ─────────────────

_MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/reports/summary.xlsx")
def summary_xlsx(desde: str | None = None, hasta: str | None = None,
                 user: dict = Depends(require_superadmin)):
    contenido = exporters.xlsx_resumen(user, desde, hasta)
    return Response(content=contenido, media_type=_MIME_XLSX,
                    headers={"Content-Disposition": "attachment; filename=parkium_resumen.xlsx"})


@router.get("/reports/summary.pdf")
def summary_pdf(desde: str | None = None, hasta: str | None = None,
                user: dict = Depends(require_superadmin)):
    contenido = exporters.pdf_resumen(user, desde, hasta)
    return Response(content=contenido, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=parkium_resumen.pdf"})


@router.get("/reports/full.xlsx")
def full_xlsx(desde: str | None = None, hasta: str | None = None,
              user: dict = Depends(require_superadmin)):
    """XLSX completo: 5 hojas + 2 gráficos (docs/04 §4.9)."""
    contenido = exporters.xlsx_completo(user, desde, hasta)
    return Response(content=contenido, media_type=_MIME_XLSX,
                    headers={"Content-Disposition": "attachment; filename=parkium_completo.xlsx"})


@router.get("/clock/status")
def clock_status(user: dict = Depends(get_current_user)):
    from ..domain import time_integrity
    return time_integrity.clock_status_summary()


@router.post("/clock/verify")
def clock_verify(user: dict = Depends(get_current_user)):
    """docs/09 tarea 5.4: con fuente externa; sin ella el cobro sigue (docs/12 §10)."""
    from ..domain import time_integrity
    return time_integrity.verify_clock(usar_red=True)
