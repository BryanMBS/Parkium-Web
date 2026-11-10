"""Renderizado de comprobantes para impresión (docs/04 §4.4).

Genera en SVG:
- el código QR (apunta a /r/{token}) con ``qrcode``, y
- el código de barras Code128 (placa del vehículo) con ``python-barcode``.

Ambos en SVG para que se impriman nítidos desde el navegador o se envíen a una
impresora térmica que acepte SVG.
"""
from __future__ import annotations

import io

import qrcode
from qrcode.image.svg import SvgPathImage
from barcode import Code128
from barcode.writer import SVGWriter

MODULO_QR = 4  # tamaño de módulo del QR en el SVG
ANCHO_TICKET_MM = 80  # ticket de 80 mm de ancho


def qr_svg(payload: str, modulo: int = MODULO_QR) -> str:
    """Devuelve un SVG con el código QR que apunta al comprobante público."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=modulo,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    factory = SvgPathImage
    img = qr.make_image(image_factory=factory)
    buf = io.BytesIO()
    img.save(buf, kind="SVG")
    svg = buf.getvalue().decode("utf-8")
    # qrcode ya emite un <svg> completo; lo devolvemos tal cual.
    return svg


def barcode_svg(value: str) -> str:
    """Devuelve un SVG con el código de barras Code128 del ``value``."""
    if not value:
        value = " "
    buf = io.BytesIO()
    Code128(value, writer=SVGWriter()).write(buf)
    svg = buf.getvalue().decode("utf-8")
    return svg


def _svg_escape(texto: str) -> str:
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def ticket_svg(data: dict) -> str:
    """SVG completo del ticket (80 mm) con líneas, código de barras y QR.

    ``data`` es el cuerpo que devuelve ``receipts.receipt_lines``:
    { id, numero, tipo, parqueadero, lineas, codigo_barras, url_qr,
      mostrar_codigo_barras, mostrar_qr, terms, footer }.
    """
    lineas = data.get("lineas", []) or []
    nombre = (data.get("parqueadero") or {}).get("nombre", "PARKIUM")
    tipo = data.get("tipo", "")
    numero = data.get("numero", "")
    mostrar_barras = bool(data.get("mostrar_codigo_barras", True))
    mostrar_qr = bool(data.get("mostrar_qr", True))
    codigo_barras = data.get("codigo_barras") or ""
    url_qr = data.get("url_qr") or ""
    terms = data.get("terms")
    footer = data.get("footer") or ""

    # Cada línea ~5 mm de alto; estimamos alto dinámico.
    alto_linea = 5.2
    alto_cuerpo = len(lineas) * alto_linea + 20
    alto_barras = 14 if mostrar_barras else 0
    alto_qr = 34 if mostrar_qr else 0
    alto_extra = (10 if terms else 0) + (8 if footer else 0)
    alto_total = alto_cuerpo + alto_barras + alto_qr + alto_extra + 30

    def texto(x: float, y: float, contenido: str, negrita: bool = False, tam: float = 3.2) -> str:
        peso = "bold" if negrita else "normal"
        return (
            f"<text x='{x}' y='{y}' font-family='Consolas, monospace' "
            f"font-size='{tam}' font-weight='{peso}' fill='#111827'>{_svg_escape(contenido)}</text>"
        )

    partes: list[str] = []
    partes.append(
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{ANCHO_TICKET_MM}mm' "
        f"height='{alto_total}mm' viewBox='0 0 {ANCHO_TICKET_MM} {alto_total}'>"
    )
    partes.append("<rect width='100%' height='100%' fill='#ffffff' />")

    y = 8
    # Cabecera: nombre del parqueadero (negrita, grande)
    partes.append(texto(4, y, nombre, negrita=True, tam=5))
    y += 5
    pk = data.get("parqueadero") or {}
    if pk.get("nit"):
        partes.append(texto(4, y, f"NIT: {_svg_escape(pk['nit'])}", tam=2.8))
        y += 4.2
    if pk.get("direccion"):
        partes.append(texto(4, y, _svg_escape(pk["direccion"]), tam=2.8))
        y += 4.2

    y += 2
    partes.append(texto(4, y, receipt_title(tipo), negrita=True, tam=4))
    y += 5
    partes.append(texto(4, y, f"Comprobante No. {numero}", tam=3.4))
    y += 4.6

    for linea in lineas:
        if linea == "":
            y += 2.6
            continue
        negrita = linea.isupper() and len(linea) > 3
        partes.append(texto(4, y, linea, negrita=negrita, tam=3.0))
        y += alto_linea

    if mostrar_barras and codigo_barras:
        y += 2
        partes.append(
            f"<g transform='translate(4, {y})'>{barcode_svg(codigo_barras)}</g>"
        )
        y += alto_barras

    if mostrar_qr and url_qr:
        y += 2
        qr_svg_ = qr_svg(url_qr)
        # incrustamos el SVG del QR como un grupo tras escalarlo a ~28 mm
        qr_inner = qr_svg_.replace("<svg ", "<g ").replace("</svg>", "</g>")
        partes.append(
            f"<g transform='translate({ANCHO_TICKET_MM - 32}, {y}) scale(0.7)'>{qr_inner}</g>"
        )
        y += alto_qr

    if terms:
        y += 4
        partes.append(texto(4, y, _svg_escape(terms), tam=2.6))
        y += 10

    if footer:
        partes.append(texto(4, y, _svg_escape(footer), tam=2.8))

    partes.append("</svg>")
    return "".join(partes)


def receipt_title(kind: str) -> str:
    return {
        "ENTRY": "Factura de ingreso",
        "EXIT": "Recibo de pago",
        "SUBSCRIPTION": "Recibo mensualidad",
        "ADJUSTMENT": "Recibo de ajuste",
    }.get(kind, "Comprobante")
