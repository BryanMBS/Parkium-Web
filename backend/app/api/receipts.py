"""Comprobantes, reimpresión y recibo público (docs/04 §4.4, 4.13)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response

from ..deps import get_current_user
from ..domain import receipts as rec
from ..domain import receipt_render as render
from ..domain.errors import NotFoundError

router = APIRouter(tags=["comprobantes"])


@router.get("/api/receipts/{receipt_id}/preview")
def preview(receipt_id: int, user: dict = Depends(get_current_user)):
    data = rec.receipt_lines(receipt_id, user.get("tenant_id"))
    if not data:
        raise NotFoundError("El comprobante no existe.")
    return data


@router.get("/api/receipts/{receipt_id}/qr.svg")
def qr_svg_endpoint(receipt_id: int, user: dict = Depends(get_current_user)):
    """SVG del código QR que apunta al comprobante público /r/{token}."""
    data = rec.receipt_lines(receipt_id, user.get("tenant_id"))
    if not data:
        raise NotFoundError("El comprobante no existe.")
    url_qr = data.get("url_qr") or ""
    if not url_qr:
        raise NotFoundError("El comprobante no tiene URL pública de QR.")
    svg = render.qr_svg(url_qr)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/api/receipts/{receipt_id}/barcode.svg")
def barcode_svg_endpoint(receipt_id: int, user: dict = Depends(get_current_user)):
    """SVG del código de barras Code128 con la placa del vehículo."""
    data = rec.receipt_lines(receipt_id, user.get("tenant_id"))
    if not data:
        raise NotFoundError("El comprobante no existe.")
    svg = render.barcode_svg(data.get("codigo_barras") or "")
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/api/receipts/{receipt_id}/ticket.svg")
def ticket_svg_endpoint(receipt_id: int, user: dict = Depends(get_current_user)):
    """SVG completo del ticket (80 mm) listo para imprimir."""
    data = rec.receipt_lines(receipt_id, user.get("tenant_id"))
    if not data:
        raise NotFoundError("El comprobante no existe.")
    svg = render.ticket_svg(data)
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/api/receipts/{receipt_id}/reprint")
def reprint(receipt_id: int, user: dict = Depends(get_current_user)):
    return rec.reprint_receipt(user, receipt_id)


@router.get("/r/{token}", response_class=HTMLResponse)
def public_receipt(token: str):
    """Ruta PÚBLICA fuera de /api, sin autenticación, por token (docs/04 §4.13)."""
    data = rec.public_receipt_by_token(token)
    if not data:
        raise NotFoundError("Comprobante no encontrado.")
    html = rec.public_page_html(data)
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})
