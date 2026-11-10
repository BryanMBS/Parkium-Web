"""Comprobantes (docs/05 §4): emitir, consultar, reimpresión y QR público.

Numeración consecutiva POR SEDE reservada dentro de la transacción del
cobro; el QR apunta a la URL pública /r/{token} que resuelve sólo con
su token; la reimpresión incrementa el contador y audita.
"""
from __future__ import annotations

import html
from decimal import Decimal

from ..config import settings
from ..db import query, query_one, transaction
from . import authentication as auth, time_utils
from .errors import DomainError, NotFoundError
from .parking_operations import normalise_plate


def next_receipt_number(site_id: int) -> int:
    row = query_one("SELECT next_number FROM receipt_counters WHERE site_id = ?", (site_id,))
    return int(row["next_number"]) if row else 1


def receipt_title(kind: str) -> str:
    return {
        "ENTRY": "Factura de ingreso",
        "EXIT": "Recibo de pago",
        "SUBSCRIPTION": "Recibo mensualidad",
        "ADJUSTMENT": "Recibo de ajuste",
    }[kind]


def barcode_value(plate: str) -> str:
    """Code128 con la placa en mayúsculas; respaldo: número del documento."""
    return (plate or "").upper()


def receipt_lines(receipt_id: int, tenant_id: int | None = None) -> dict | None:
    """Datos del comprobante para vista previa e impresión (docs/04 §4.4).
    Con tenant_id: sólo comprobantes del tenant de la sesión."""
    receipt = query_one("SELECT * FROM receipts WHERE id = ?", (receipt_id,))
    if not receipt:
        return None
    if tenant_id is not None and receipt["tenant_id"] != tenant_id:
        return None
    template = query_one(
        "SELECT * FROM receipt_templates WHERE site_id = ? AND is_active = 1 ORDER BY id LIMIT 1",
        (receipt["site_id"],))
    site_row = query_one("SELECT * FROM parking_sites WHERE id = ?", (receipt["site_id"],))
    stay = query_one(
        "SELECT s.*, v.plate, v.vehicle_type_id, tv.name AS tipo_nombre "
        "FROM parking_stays s JOIN vehicles v ON v.id = s.vehicle_id "
        "JOIN vehicle_types tv ON tv.id = v.vehicle_type_id WHERE s.id = ?",
        (receipt["stay_id"],)) if receipt["stay_id"] else None
    payment = query_one("SELECT * FROM payments WHERE id = ?", (receipt["payment_id"],)) if receipt["payment_id"] else None
    method = query_one("SELECT name FROM payment_methods WHERE id = ?", (payment["payment_method_id"],)) if payment else None
    sub = None
    if payment and payment["subscription_id"]:
        sub = query_one("SELECT * FROM subscriptions WHERE id = ?", (payment["subscription_id"],))
    tz = site_row["timezone"]

    lineas: list[str] = []
    nombre = (template or {}).get("parking_name") or "PARKIUM"
    nit = (template or {}).get("nit") or site_row.get("tax_id") or ""
    direccion = (template or {}).get("address") or site_row.get("address") or ""
    encabezado = (template or {}).get("header_text")

    lineas.append(nombre)
    if nit:
        lineas.append(f"NIT: {nit}")
    if direccion:
        lineas.append(direccion)
    if encabezado:
        lineas.append(encabezado)
    lineas.append("")
    lineas.append(receipt_title(receipt["receipt_type"]))
    lineas.append(f"Comprobante No. {receipt['receipt_number']}")
    lineas.append(f"Fecha: {time_utils.local_str(time_utils.parse_iso(receipt['issued_at']), {'timezone': tz})}")
    if stay:
        minutes = time_utils.elapsed_minutes(stay["entry_at"],
                                             time_utils.parse_iso(stay["exit_at"]) if stay["exit_at"] else None)
        lineas.append(f"Placa: {stay['plate']} - {stay['tipo_nombre']}")
        lineas.append(f"Ingreso: {time_utils.local_str(time_utils.parse_iso(stay['entry_at']), {'timezone': tz})}")
        if stay["exit_at"]:
            lineas.append(f"Salida: {time_utils.local_str(time_utils.parse_iso(stay['exit_at']), {'timezone': tz})}")
            lineas.append(f"Tiempo: {minutes} min")
        if payment:
            lineas.append(f"Importe: ${Decimal(str(payment['amount'])):,.2f}")
            lineas.append(f"Forma de pago: {method['name'] if method else '-'}")
            if payment["amount_received"] is not None:
                lineas.append(f"Recibido: ${Decimal(str(payment['amount_received'])):,.2f}")
            if payment["change_amount"] is not None:
                lineas.append(f"Cambio: ${Decimal(str(payment['change_amount'])):,.2f}")
    if sub:
        lineas.append(f"Cliente plan: {sub['plan_name']}")
        lineas.append(f"Importe: ${Decimal(str(sub['amount'])):,.2f}")
    return {
        "id": receipt["id"], "numero": receipt["numero"] if "numero" in receipt else receipt["receipt_number"],
        "tipo": receipt["receipt_type"],
        "parqueadero": {"nombre": nombre, "nit": nit, "direccion": direccion},
        "lineas": lineas,
        "codigo_barras": barcode_value(stay["plate"]) if stay else "",
        "url_qr": receipt_url(receipt),
        "mostrar_codigo_barras": bool((template or {}).get("show_barcode", 1)),
        "mostrar_qr": bool((template or {}).get("show_qr", 1)),
        "terms": (template or {}).get("terms_text"),
        "footer": (template or {}).get("footer_text") or "",
    }


def receipt_url(receipt) -> str:
    base = settings.url_publica_base.rstrip("/")
    return f"{base}/r/{receipt['qr_payload']}" if receipt.get("qr_payload") else ""


def public_receipt_by_token(token: str) -> dict | None:
    receipt = query_one("SELECT * FROM receipts WHERE qr_payload = ?", (token,))
    if not receipt:
        return None
    return receipt_lines(receipt["id"])


def reprint_receipt(user: dict, receipt_id: int, tipo: str | None = None) -> dict:
    """Reimpresión con contador y auditoría (docs/09 tarea 4.5)."""
    receipt = query_one(
        "SELECT * FROM receipts WHERE id = ? AND tenant_id = ?",
        (receipt_id, user["tenant_id"]))
    if not receipt:
        raise NotFoundError()
    with transaction() as conn:
        conn.execute(
            "UPDATE receipts SET reprint_count = reprint_count + 1 WHERE id = ?", (receipt_id,))
        nuevo = conn.execute("SELECT reprint_count FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
        auth._audit(conn, user["id"], "receipt", receipt_id, "RECEIPT_REPRINTED", None,
                    {"reprint_count": nuevo["reprint_count"], "tipo": tipo or receipt["receipt_type"]})
    return {"id": receipt_id, "reprint_count": nuevo["reprint_count"]}


def public_page_html(data: dict) -> str:
    """Vista pública mínima del comprobante: /r/{token} (docs/04 §4.13)."""
    lineas = "\n".join(
        f"<p class='l {'title' if i == 0 and data['lineas'][0] == l else ''}'>{html.escape(l)}</p>"
        for i, l in enumerate(data.get("lineas", [])) if l != "" or True)
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<title>Comprobante {html.escape(str(data.get('numero', '')))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: 'JetBrains Mono', Consolas, monospace; background: #0B1120; color: #E2E8F0;
         display: grid; place-items: center; min-height: 100vh; margin: 0; }}
  .ticket {{ background: #151C2E; border: 1px solid #2A3550; border-radius: 12px;
            padding: 24px 28px; max-width: 380px; width: 100%; }}
  .l {{ margin: 4px 0; font-size: 14px; }}
  .title {{ font-weight: bold; color: #A3E635; }}
  h1 {{ font-size: 16px; color: #C4B5FD; }}
</style></head>
<body><div class="ticket"><h1>PARKIUM</h1>{lineas}</div></body></html>"""
