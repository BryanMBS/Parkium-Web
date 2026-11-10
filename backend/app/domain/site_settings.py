"""Datos del parqueadero y plantilla de comprobante (docs/05 §8).

Los datos fiscales y la plantilla son SOLO super administrador,
y ambos cambios quedan auditados (docs/07 §7.6). Multi-tenant: las
operaciones resuelven la sede del TENANT de la sesión (su primera
sede activa), nunca DEFAULT_SITE_ID global.
"""
from __future__ import annotations

import json

from ..db import query_one, transaction
from . import authentication as auth
from . import time_utils
from .errors import AuthorizationError, NotFoundError
from .parking_operations import site

DEFAULT_TERMS = "TÉRMINOS Y CONDICIONES\nEste comprobante es un documento interno del parqueadero. No constituye facturación electrónica."
DEFAULT_FOOTER = "PARKIUM - Todos los derechos reservados."


def _tid(user: dict) -> int:
    tid = (user or {}).get("tenant_id")
    if not tid:
        raise AuthorizationError("La petición requiere una sesión de tenant.")
    return int(tid)


def get_site(user: dict | None = None) -> dict | None:
    tid = _tid(user) if user else int(query_one(
        "SELECT id FROM tenants ORDER BY id LIMIT 1")["id"])  # lectura pública interna
    s = query_one(
        "SELECT * FROM parking_sites WHERE tenant_id = ? AND is_active = 1 ORDER BY id LIMIT 1",
        (tid,))
    if s:
        s["timezone_label"] = s["timezone"]
    return s


def update_site(user: dict, datos: dict, ip=None) -> dict:
    auth.require_superadmin(user)
    tid = _tid(user)
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM parking_sites WHERE tenant_id = ? AND is_active = 1 "
            "ORDER BY id LIMIT 1", (tid,)).fetchone()
        if not row:
            raise NotFoundError()
        antes = dict(row)
        conn.execute(
            "UPDATE parking_sites SET name = ?, tax_id = ?, address = ?, phone = ?, total_capacity = ? "
            "WHERE id = ?",
            (datos.get("nombre", antes["name"]), datos.get("nit", antes["tax_id"]),
             datos.get("direccion", antes["address"]), datos.get("telefono", antes["phone"]),
             datos.get("capacidad_total", antes["total_capacity"]), antes["id"]))
        auth._audit(conn, user["id"], "parking_site", antes["id"],
                    "SITE_UPDATED",
                    {"nombre": antes["name"], "nit": antes["tax_id"]},
                    {k: v for k, v in datos.items()}, ip)
    return get_site(user)


def get_receipt_template(site_id: int | None = None) -> dict:
    """Sin site_id: plantilla de la primera sede del sistema (uso de scripts).
    Las rutas operativas pasan la site_id del tenant."""
    if site_id is None:
        r = query_one("SELECT id FROM parking_sites ORDER BY id LIMIT 1")
        site_id = int(r["id"]) if r else 1
    plantilla = query_one(
        "SELECT * FROM receipt_templates WHERE site_id = ? AND is_active = 1 ORDER BY id LIMIT 1",
        (site_id,))
    if not plantilla:
        return {
            "nombre_plantilla": "Plantilla predeterminada", "nombre_parqueadero": "PARKIUM",
            "nit": None, "direccion": None, "encabezado": None,
            "terminos": DEFAULT_TERMS, "pie": DEFAULT_FOOTER,
            "mostrar_codigo_barras": True, "mostrar_qr": True,
        }
    return {
        "id": plantilla["id"], "nombre_plantilla": plantilla["template_name"],
        "nombre_parqueadero": plantilla["parking_name"], "nit": plantilla["nit"],
        "direccion": plantilla["address"], "encabezado": plantilla["header_text"],
        "terminos": plantilla["terms_text"] or DEFAULT_TERMS,
        "pie": plantilla["footer_text"] or DEFAULT_FOOTER,
        "mostrar_codigo_barras": bool(plantilla["show_barcode"]),
        "mostrar_qr": bool(plantilla["show_qr"]),
    }


def update_receipt_template(user: dict, datos: dict, site_id: int | None = None,
                            ip=None) -> dict:
    auth.require_superadmin(user)
    tid = _tid(user)
    if site_id is None:
        sede = query_one(
            "SELECT id FROM parking_sites WHERE tenant_id = ? AND is_active = 1 "
            "ORDER BY id LIMIT 1", (tid,))
        if not sede:
            raise NotFoundError()
        site_id = int(sede["id"])
    # la plantilla siempre pertenece a una sede del mismo tenant
    if not query_one("SELECT id FROM parking_sites WHERE id = ? AND tenant_id = ?",
                     (site_id, tid)):
        raise NotFoundError()
    with transaction() as conn:
        fila = conn.execute(
            "SELECT * FROM receipt_templates WHERE site_id = ? ORDER BY id LIMIT 1", (site_id,)).fetchone()
        before = dict(fila) if fila else None
        if fila:
            conn.execute(
                "UPDATE receipt_templates SET template_name = ?, parking_name = ?, nit = ?, address = ?, "
                "header_text = ?, terms_text = ?, footer_text = ?, show_barcode = ?, show_qr = ?, "
                "updated_by_user_id = ?, updated_at = ? WHERE id = ?",
                (datos.get("nombre_plantilla", fila["template_name"]),
                 datos.get("nombre_parqueadero", fila["parking_name"]),
                 datos.get("nit", fila["nit"]), datos.get("direccion", fila["address"]),
                 datos.get("encabezado", fila["header_text"]),
                 datos.get("terminos", fila["terms_text"]),
                 datos.get("pie", fila["footer_text"]),
                 1 if datos.get("mostrar_codigo_barras", bool(fila["show_barcode"])) else 0,
                 1 if datos.get("mostrar_qr", bool(fila["show_qr"])) else 0,
                 user["id"], time_utils.iso_utc(),
                 fila["id"]))
            template_id = fila["id"]
        else:
            conn.execute(
                "INSERT INTO receipt_templates (site_id, tenant_id, template_name, parking_name, nit, address, "
                "header_text, terms_text, footer_text, show_barcode, show_qr, updated_by_user_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (site_id, tid, datos.get("nombre_plantilla", "Plantilla predeterminada"),
                 datos.get("nombre_parqueadero", "PARKIUM"), datos.get("nit"),
                 datos.get("direccion"), datos.get("encabezado"),
                 datos.get("terminos", DEFAULT_TERMS), datos.get("pie", DEFAULT_FOOTER),
                 1 if datos.get("mostrar_codigo_barras", True) else 0,
                 1 if datos.get("mostrar_qr", True) else 0, user["id"]))
            template_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        auth._audit(conn, user["id"], "receipt_template", template_id, "RECEIPT_TEMPLATE_UPDATED",
                    {k: v for k, v in (before or {}).items() if k in ("nit", "parking_name")},
                    {k: v for k, v in datos.items()}, ip)
    return get_receipt_template(site_id)
