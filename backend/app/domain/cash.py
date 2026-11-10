"""Caja por turno (docs/01 §1.1, módulo cash.py).

Un turno abierto por usuario y sede; el esperado suma sólo los cobros
en efectivo (docs/11 §11.6).
"""
from __future__ import annotations

from decimal import Decimal

from ..db import query, query_one, transaction
from . import authentication as auth, time_utils
from .errors import ConflictError, DomainError, NotFoundError


def open_cash_shift(user: dict, monto_inicial: Decimal | str = "0", ip=None) -> dict:
    from .parking_operations import _tid, site
    tid = _tid(user)
    site_row = site(tid)
    site_id = site_row["id"]
    abierto = query_one(
        "SELECT * FROM cash_shifts WHERE site_id = ? AND user_id = ? AND status = 'OPEN'",
        (site_id, user["id"]))
    if abierto:
        raise ConflictError("Ya tiene un turno de caja abierto.")
    with transaction() as conn:
        conn.execute(
            "INSERT INTO cash_shifts (site_id, tenant_id, user_id, opened_at, opening_amount, status) "
            "VALUES (?,?,?,?,?, 'OPEN')",
            (site_id, tid, user["id"], time_utils.iso_utc(), Decimal(str(monto_inicial))))
        shift_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        auth._audit(conn, user["id"], "cash_shift", shift_id, "CASH_SHIFT_OPENED", None,
                    {"monto_inicial": str(monto_inicial)}, ip)
    return get_cash_shift(shift_id, tid)


def list_open_shifts(user: dict) -> list[dict]:
    return query(
        "SELECT s.*, u.username FROM cash_shifts s JOIN users u ON u.id = s.user_id "
        "WHERE s.status = 'OPEN' AND s.tenant_id = ? ORDER BY s.opened_at DESC",
        (user["tenant_id"],))


def get_cash_shift(shift_id: int, tenant_id: int | None = None) -> dict | None:
    """Con tenant_id exige que el turno pertenezca a ese tenant."""
    if tenant_id is None:
        return query_one(
            "SELECT s.*, u.username FROM cash_shifts s JOIN users u ON u.id = s.user_id WHERE s.id = ?",
            (shift_id,))
    return query_one(
        "SELECT s.*, u.username FROM cash_shifts s JOIN users u ON u.id = s.user_id "
        "WHERE s.id = ? AND s.tenant_id = ?", (shift_id, tenant_id))


def expected_cash(user: dict, shift_id: int) -> dict:
    shift = get_cash_shift(shift_id, user["tenant_id"])
    if not shift:
        raise NotFoundError()
    row = query_one(
        "SELECT count(*) AS pagos, COALESCE(SUM(amount), 0) AS total FROM payments "
        "WHERE cash_shift_id = ? AND tenant_id = ? AND status = 'APPROVED' AND payment_method_id = 1",
        (shift_id, user["tenant_id"]))
    apertura = Decimal(str(shift["opening_amount"] or 0))
    esperado = apertura + Decimal(str(row["total"] if row else 0))
    return {
        "turno_id": shift_id, "esperado": _m(esperado), "apertura": _m(apertura),
        "cobros_efectivo": row["pagos"] if row else 0,
    }


def close_cash_shift(user: dict, shift_id: int, monto_contado: Decimal | str, ip=None) -> dict:
    esperados = expected_cash(user, shift_id)
    esperado = Decimal(esperados["esperado"])
    contado = Decimal(str(monto_contado))
    shift = get_cash_shift(shift_id, user["tenant_id"])
    if not shift:
        raise NotFoundError()
    if shift["status"] != "OPEN":
        raise DomainError("El turno ya está cerrado.")
    if shift["user_id"] != user["id"] and not auth.require_admin(user):
        raise ConflictError("Sólo el dueño del turno o un administrador puede cerrarlo.")
    diferencia = contado - esperado
    with transaction() as conn:
        conn.execute(
            "UPDATE cash_shifts SET closed_at = ?, expected_amount = ?, counted_amount = ?, "
            "difference_amount = ?, status = 'CLOSED' WHERE id = ?",
            (time_utils.iso_utc(), esperado, contado, diferencia, shift_id))
        auth._audit(conn, user["id"], "cash_shift", shift_id, "CASH_SHIFT_CLOSED",
                    {"estado": "OPEN"},
                    {"esperado": _m(esperado), "contado": _m(contado), "diferencia": _m(diferencia)}, ip)
    return {"esperado": _m(esperado), "contado": _m(contado),
            "diferencia": _m(diferencia), "estado": "CLOSED"}


def _m(d: Decimal) -> str:
    from .parking_operations import money
    return money(d)
