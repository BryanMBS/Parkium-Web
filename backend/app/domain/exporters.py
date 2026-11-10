"""Exportaciones XLSX y PDF (docs/05 §9, docs/04 §4.9).

- `GET /api/reports/summary.xlsx`: XLSX de **una hoja** (Resumen, con los
  cortes apilados debajo).
- `GET /api/reports/full.xlsx`:    XLSX completo — **5 hojas y 2 gráficos**
  (barras por forma de pago y torta por tipo de vehículo).
- `GET /api/reports/summary.pdf`:  PDF del resumen con el estilo de marca de
  docs/06 §2: encabezado DARK `#1B1F2A`, acento LIME `#A3E635`, secciones
  PURPLE `#5B21B6`.

El PDF se dibuja a mano con las fuentes base de PDF (Helvetica, WinAnsi) por el
mismo motivo por el que los comprobantes salen en SVG: no añadir dependencias de
renderizado. En XLSX los importes se escriben como número con formato
`#,##0.00` para que Excel pueda sumar; el contrato de «cadena decimal» es para
JSON (docs/04 §4.9). En el PDF se pintan en formato colombiano `$45.000,00`
(docs/12 §7).

Estas exportaciones son SÓLO super administrador: el control vive en
`reports.operation_summary` (docs/05 §9 «Exportación completa: sólo super admin»).
"""
from __future__ import annotations

import io
from datetime import datetime
from decimal import Decimal

_CORTES: tuple[tuple[str, str], ...] = (
    ("Por forma de pago", "por_metodo"),
    ("Por tipo de vehículo", "por_tipo_vehiculo"),
    ("Por empleado", "por_empleado"),
    ("Por tarifa", "por_tarifa"),
)


# ────────────────────── Utilidades de datos ───────────────────────────

def _datos(user: dict, desde: str | None, hasta: str | None) -> dict:
    # import tardío para evitar el ciclo exporters -> reports -> exporters
    from . import reports as _reports
    return _reports.operation_summary(user, desde, hasta)


def _lista_corte(datos: dict, clave: str) -> list[tuple[str, str, int]]:
    """[(etiqueta, valor, cantidad), …] con importes como cadena (docs/04 §4.1)."""
    return [(f["etiqueta"], f["valor"], f["cantidad"]) for f in (datos.get(clave) or [])]


def _dec(s: str) -> Decimal:
    return Decimal(str(s) or "0")


def _colombiano(s: str) -> str:
    """`45.000,00` — docs/12 §7. Entrada: cadena decimal («45123.45»)."""
    neg = s.startswith("-")
    cuerpo = s[1:] if neg else s
    entero, _, decimal = cuerpo.partition(".")
    entero = entero.lstrip("0") or "0"
    dec = (decimal + "00")[:2]
    grupos: list[str] = []
    while len(entero) > 3:
        grupos.insert(0, entero[-3:])
        entero = entero[:-3]
    grupos.insert(0, entero)
    return ("-" if neg else "") + ".".join(grupos) + "," + dec


def _fecha_es(fecha: str) -> str:
    """YYYY-MM-DD -> DD/MM/YYYY."""
    y, m, d = fecha[:10].split("-")
    return f"{d}/{m}/{y}"


def _ahora() -> str:
    return datetime.utcnow().strftime("%d/%m/%Y %H:%M") + " UTC"


# ────────────────────────── XLSX (openpyxl) ───────────────────────────

_PRIMARY = "5B21B6"      # acción principal (docs/06 §2)
_LIME = "A3E635"
_DARK = "1B1F2A"
_MUTED = "64748B"
_NUMERO = "#,##0.00"


def _estilos() -> dict:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    return {
        "cabecera_f": Font(bold=True, color="FFFFFF"),
        "cabecera_fill": PatternFill("solid", fgColor=_PRIMARY),
        "titulo": Font(bold=True, size=14, color=_DARK),
        "sub": Font(size=9, color=_MUTED),
        "seccion": Font(bold=True, size=11, color=_PRIMARY),
        "tenue": Font(italic=True, color=_MUTED),
        "borde": Border(bottom=Side(style="thin", color="E2E8F0")),
        "centro": Alignment(horizontal="center"),
        "derecha": Alignment(horizontal="right"),
    }


def _corte_a_hoja(ws, e: dict, fila: int, filas: list) -> int:
    """Tabla «Concepto | Cobros | Importe»; devuelve la fila siguiente libre."""
    for c, v in enumerate(("Concepto", "Cobros", "Importe"), start=1):
        cell = ws.cell(row=fila, column=c, value=v)
        cell.font = e["cabecera_f"]
        cell.fill = e["cabecera_fill"]
        cell.alignment = e["centro"] if c == 1 else e["derecha"]
    fila += 1
    for etiqueta, valor, cantidad in filas:
        ws.cell(row=fila, column=1, value=etiqueta)
        ws.cell(row=fila, column=2, value=cantidad).alignment = e["derecha"]
        ws.cell(row=fila, column=2).number_format = "0"
        ws.cell(row=fila, column=3, value=float(_dec(valor))).alignment = e["derecha"]
        ws.cell(row=fila, column=3).number_format = _NUMERO
        fila += 1
    if not filas:
        ws.cell(row=fila, column=1, value="Sin datos en el rango.").font = e["tenue"]
        fila += 1
    return fila + 2


def _escribe_resumen(ws, datos: dict, e: dict, con_secciones: bool) -> None:
    ws["A1"] = "Parkium — Consolidado de operación"
    ws["A1"].font = e["titulo"]
    ws["A2"] = (f"Rango: {datos['desde']} a {datos['hasta']} · generado: {_ahora()} · "
                "documento interno, no es facturación electrónica (docs/12 §4)")
    ws["A2"].font = e["sub"]
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 16

    fila = 4
    for c, v in enumerate(("Concepto", "Importe"), start=1):
        cell = ws.cell(row=fila, column=c, value=v)
        cell.font = e["cabecera_f"]
        cell.fill = e["cabecera_fill"]
        cell.alignment = e["centro"] if c == 1 else e["derecha"]
    fila += 1
    for concepto, importe in (
            ("Rotación (estadías)", datos["rotacion"]),
            ("Mensualidades", datos["mensualidades"]),
            ("Total facturado", datos["total"])):
        cell = ws.cell(row=fila, column=1, value=concepto)
        if concepto.startswith("Total"):
            cell.font = e["seccion"]
        ws.cell(row=fila, column=2, value=float(_dec(importe))).alignment = e["derecha"]
        ws.cell(row=fila, column=2).number_format = _NUMERO
        fila += 1

    if con_secciones:
        fila += 3
        for nombre, clave in _CORTES:
            ws.cell(row=fila, column=1, value=nombre).font = e["seccion"]
            fila = _corte_a_hoja(ws, e, fila + 1, _lista_corte(datos, clave))


def _escribe_hoja_corte(ws, nombre: str, datos: dict, clave: str, e: dict) -> None:
    ws["A1"] = nombre
    ws["A1"].font = e["titulo"]
    ws["A2"] = ("Fuente: pagos APPROVED del rango del resumen; "
                "hoja complementaria de la exportación completa (docs/05 §9).")
    ws["A2"].font = e["sub"]
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 16
    ws.freeze_panes = "A5"
    _corte_a_hoja(ws, e, 4, _lista_corte(datos, clave))


def _graficos(wb, datos: dict) -> None:
    """Los 2 gráficos del XLSX completo (docs/05 §9): barras y torta."""
    from openpyxl.chart import BarChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList

    resumen = wb["Resumen"]
    especificaciones = (
        ("Por forma de pago", "por_metodo", BarChart,
         "Importe por forma de pago", "A8"),
        ("Por tipo de vehículo", "por_tipo_vehiculo", PieChart,
         "Distribución por tipo de vehículo", "A26"),
    )
    for nombre_hoja, clave, tipo, titulo, ancla in especificaciones:
        ws = wb[nombre_hoja]
        filas = _lista_corte(datos, clave)
        if not filas:
            continue
        data = Reference(ws, min_col=3, min_row=4, max_row=4 + len(filas))
        cats = Reference(ws, min_col=1, min_row=5, max_row=4 + len(filas))
        grafico = tipo()
        grafico.title = titulo
        grafico.add_data(data, titles_from_data=True)
        grafico.set_categories(cats)
        grafico.height, grafico.width = 8.5, 15
        grafico.dataLabels = DataLabelList()
        if isinstance(grafico, BarChart):
            grafico.y_axis.title = "Importe"
            grafico.dataLabels.showVal = True
        else:
            grafico.dataLabels.showPercent = True
        resumen.add_chart(grafico, ancla)


def _libro():
    from openpyxl import Workbook
    return Workbook()


def xlsx_resumen(user: dict, desde: str | None = None, hasta: str | None = None) -> bytes:
    """`GET /api/reports/summary.xlsx` — una hoja (docs/04 §4.9)."""
    datos = _datos(user, desde, hasta)
    e = _estilos()
    wb = _libro()
    ws = wb.active
    ws.title = "Resumen"
    ws.sheet_properties.tabColor = _PRIMARY
    _escribe_resumen(ws, datos, e, con_secciones=True)
    wb.properties.title = "Parkium — Consolidado de operación"
    wb.properties.creator = "Parkium Web"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def xlsx_completo(user: dict, desde: str | None = None, hasta: str | None = None) -> bytes:
    """`GET /api/reports/full.xlsx` — 5 hojas + 2 gráficos (docs/05 §9).

    Hojas: Resumen, Por forma de pago, Por tipo de vehículo, Por empleado y
    Por tarifa. Los gráficos viven en «Resumen» alimentándose de sus hojas de
    origen (checklist 11.10: «el gráfico del XLSX coincide con el dashboard»).
    """
    datos = _datos(user, desde, hasta)
    e = _estilos()
    wb = _libro()
    ws = wb.active
    ws.title = "Resumen"
    ws.sheet_properties.tabColor = _PRIMARY
    _escribe_resumen(ws, datos, e, con_secciones=False)
    for nombre, clave in _CORTES:
        hoja = wb.create_sheet(nombre)
        hoja.sheet_properties.tabColor = _LIME if clave == "por_tarifa" else "94A3B8"
        _escribe_hoja_corte(hoja, nombre, datos, clave, e)
    _graficos(wb, datos)
    wb.properties.title = "Parkium — Exportación completa de operación"
    wb.properties.creator = "Parkium Web"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─────────────────── PDF del resumen (sin dependencias) ───────────────────

_ANCHO, _ALTO = 595.28, 841.89                     # A4, en puntos
_MARGEN = 40
_BORDE_INFERIOR = 96                              # espacio reservado para el pie

_COLORES = {  # docs/06 §2
    "dark": (0.106, 0.122, 0.165),
    "lime": (0.639, 0.902, 0.208),
    "purple": (0.357, 0.129, 0.714),
    "texto": (0.067, 0.094, 0.153),
    "muted": (0.392, 0.455, 0.545),
    "borde": (0.886, 0.910, 0.941),
    "superficie_alt": (0.945, 0.961, 0.976),
    "lila": (0.941, 0.925, 0.992),
    "white": (1.0, 1.0, 1.0),
}


def _rgb(nombre: str) -> str:
    return " ".join(f"{v:.3f}" for v in _COLORES[nombre])


def _texto_pdf(texto: str) -> str:
    return texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _pdf_txt(ops: list[str], x: float, y: float, texto: str, tam: float,
             negrita: bool, color: str) -> None:
    fuente = "F2" if negrita else "F1"
    ops.append(f"{_rgb(color)} rg BT /{fuente} {tam:.2f} Tf "
               f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_texto_pdf(texto)}) Tj ET")


def _pdf_rect(ops: list[str], x: float, y: float, w: float, h: float, color: str) -> None:
    ops.append(f"{_rgb(color)} rg {x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")


def _pdf_linea(ops: list[str], x1: float, y: float, x2: float) -> None:
    ops.append(f"q {_rgb('borde')} RG 0.5 w {x1:.2f} {y:.2f} m {x2:.2f} {y:.2f} l S Q")


class _Pdf:
    """A4 con cabecera de marca y paginación por sección."""

    def __init__(self, datos: dict) -> None:
        self.datos = datos
        self.paginas: list[list[str]] = []
        self.ops: list[str] = []
        self.y = 0.0
        self._pagina(True)

    def _pagina(self, completa: bool) -> None:
        if self.ops:
            self.paginas.append(self.ops)
        h = 64 if completa else 40
        ops = [f"{_rgb('dark')} rg 0 {_ALTO - h:.2f} {_ANCHO:.2f} {h:.2f} re f",
               f"{_rgb('lime')} rg 0 {_ALTO - h:.2f} 6 {h:.2f} re f"]
        y_t = _ALTO - h + (16 if completa else 14)
        if completa:
            _pdf_txt(ops, _MARGEN, y_t + 6, "Parkium — Consolidado de operación",
                     15, True, "white")
            _pdf_txt(ops, _MARGEN, y_t - 14,
                     f"Rango: {_fecha_es(self.datos['desde'])} – "
                     f"{_fecha_es(self.datos['hasta'])}  ·  generado: {_ahora()}",
                     9, False, "white")
        else:
            _pdf_txt(ops, _MARGEN, y_t, "Parkium — Consolidado de operación (continuación)",
                     11, True, "white")
        self.ops = ops
        self.y = _ALTO - h - 28

    def hay_espacio(self, necesario: float) -> bool:
        return self.y - necesario >= _BORDE_INFERIOR

    def cerrar(self) -> list[bytes]:
        if self.ops:
            self.paginas.append(self.ops)
            self.ops = []
        return [("\n".join(p)).encode("cp1252", "replace") for p in self.paginas]


def pdf_resumen(user: dict, desde: str | None = None, hasta: str | None = None) -> bytes:
    """`GET /api/reports/summary.pdf` — tabla con estilo de la marca (docs/04 §4.9)."""
    datos = _datos(user, desde, hasta)
    pdf = _Pdf(datos)

    # 1) Tarjetas de totales (superficie con borde de color, docs/06 §2).
    ancho, alto, hueco = 165, 64, 13
    tarjetas = (
        ("Rotación (estadías)", datos["rotacion"], False),
        ("Mensualidades", datos["mensualidades"], False),
        ("Total facturado", datos["total"], True),
    )
    for i, (etiqueta, importe, destacada) in enumerate(tarjetas):
        x = _MARGEN + i * (ancho + hueco)
        _pdf_rect(pdf.ops, x, pdf.y - alto, ancho, alto,
                  "lila" if destacada else "superficie_alt")
        _pdf_rect(pdf.ops, x, pdf.y - alto, 3.5, alto, "lime" if destacada else "purple")
        _pdf_txt(pdf.ops, x + 12, pdf.y - 20, etiqueta, 8.5, False, "muted")
        _pdf_txt(pdf.ops, x + 12, pdf.y - 42, "$ " + _colombiano(importe), 13.5, True,
                 "purple" if destacada else "texto")
    pdf.y -= alto + 30

    # 2) Tablas de cortes, con paginación por sección.
    for nombre, clave in _CORTES:
        filas = _lista_corte(datos, clave)
        emitidas = 0
        while True:
            restantes = filas[emitidas:]
            bloque_cabecera = 46           # título + fila de encabezado
            if (not pdf.hay_espacio(bloque_cabecera + 40) and restantes) \
                    or not pdf.hay_espacio(bloque_cabecera + 16):
                pdf._pagina(False)
            _pdf_txt(pdf.ops, _MARGEN, pdf.y, nombre, 12, True, "purple")
            pdf.y -= 22
            _pdf_rect(pdf.ops, _MARGEN, pdf.y - 4, _ANCHO - 2 * _MARGEN, 20, "purple")
            _pdf_txt(pdf.ops, _MARGEN + 10, pdf.y + 2, "Concepto", 9, True, "white")
            _pdf_txt(pdf.ops, 428, pdf.y + 2, "Cobros", 9, True, "white")
            _pdf_txt(pdf.ops, 524, pdf.y + 2, "Importe", 9, True, "white")
            pdf.y -= 26

            sin_datos = not restantes
            total_filas = len(filas)
            while emitidas < total_filas:
                if not pdf.hay_espacio(20):
                    break
                i = emitidas
                if i % 2 == 0:
                    _pdf_rect(pdf.ops, _MARGEN, pdf.y - 20, _ANCHO - 2 * _MARGEN, 20,
                              "superficie_alt")
                etiqueta, valor, cantidad = filas[i]
                _pdf_txt(pdf.ops, _MARGEN + 10, pdf.y - 1, etiqueta[:44], 9.5, False, "texto")
                _pdf_txt(pdf.ops, 452, pdf.y - 1, str(cantidad), 9.5, False, "muted")
                _pdf_txt(pdf.ops, 502, pdf.y - 1, "$ " + _colombiano(valor), 9.5, True, "texto")
                _pdf_linea(pdf.ops, _MARGEN, pdf.y - 21, _ANCHO - _MARGEN)
                pdf.y -= 20
                emitidas += 1
            if sin_datos:
                _pdf_txt(pdf.ops, _MARGEN + 10, pdf.y - 1, "Sin datos en el rango.",
                         9.5, False, "muted")
                pdf.y -= 24
            if sin_datos or emitidas >= total_filas:
                break

    # 3) Pie.
    _pdf_txt(pdf.ops, _MARGEN, 44,
             "Parkium Web · documento interno — no es facturación electrónica "
             "(docs/12 §4). Importes en pesos colombianos sobre pagos APPROVED del rango.",
             7.5, False, "muted")
    return _ensamblar_pdf(pdf.cerrar())


def _ensamblar_pdf(paginas: list[bytes]) -> bytes:
    """PDF 1.4 con fuentes base (Helvetica/WinAnsi) — sin dependencias."""
    n = len(paginas)
    pagina_obj = [3 + 2 * k for k in range(n)]
    contenido_obj = [4 + 2 * k for k in range(n)]
    fuente_f1 = 3 + 2 * n                # Helvetica
    fuente_f2 = 4 + 2 * n                # Helvetica-Bold
    info_obj = 5 + 2 * n

    objetos: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Count %d /Kids [%s] >>"
         % (n, " ".join(f"{o} 0 R" for o in pagina_obj))).encode("latin-1"),
    ]
    for i, contenido in enumerate(paginas):
        objetos.append(
            ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Contents %d 0 R "
             "/Group << /S /Transparency /CS /DeviceRGB >> "
             "/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> >>"
             % (_ANCHO, _ALTO, contenido_obj[i], fuente_f1, fuente_f2)).encode("latin-1"))
        objetos.append(b"<< /Length %d >>\nstream\n" % len(contenido) + contenido + b"\nendstream")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica "
                   b"/Encoding /WinAnsiEncoding >>")
    objetos.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold "
                   b"/Encoding /WinAnsiEncoding >>")
    objetos.append(b"<< /Title (Parkium - Consolidado de operacion) /Creator (Parkium Web) "
                   b"/Producer (Parkium Web) >>")

    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n".encode()
    salida += b"0000000000 65535 f \n"
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R /Info {info_obj} 0 R >>\n"
               f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(salida)
