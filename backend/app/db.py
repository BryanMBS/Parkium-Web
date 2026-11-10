"""Acceso a la base de datos (SQLite en desarrollo) con una capa uniforme.

docs/03 §3.9.2: `row_factory = sqlite3.Row` se reemplaza por filas dict,
`PRAGMA foreign_keys = ON` siempre activo, y los cobros usan
`BEGIN IMMEDIATE` (docs/04 §4.13).
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

from .config import settings, SCHEMA_VERSION

# SQLite (desarrollo) no acepta Decimal como parámetro: se guarda como texto.
# Los importes SIEMPRE se leen de vuelta con Decimal(str(valor)) — nunca float
# directo (docs/04 §4.1: importes como cadena decimal).
sqlite3.register_adapter(Decimal, lambda d: format(d, "f"))

_DATA = Path(__file__).parent / "data"
_SCHEMA_PATH = _DATA / "schema.sql"
_SEED_PATH = _DATA / "seed.sql"
_lock = threading.RLock()


def _connect() -> sqlite3.Connection:
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(settings.sqlite_path), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    conn = _connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def query_one(sql: str, params: tuple = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    """Ejecuta una sentencia única en su propia transacción; devuelve lastrowid."""
    with transaction() as conn:
        cur = conn.execute(sql, params)
        return int(cur.lastrowid or 0)


@contextmanager
def transaction():
    """Transacción de escritura: BEGIN IMMEDIATE (docs/04 §4.13)."""
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def ensure_schema() -> None:
    """Crea el esquema y la semilla si no existe. Idempotente (docs/09 1.5)."""
    with _lock:
        conn = _connect()
        try:
            has_users = conn.execute(
                "SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name='users'"
            ).fetchone()
            if not has_users or not has_users["n"]:
                conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.executescript(_SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.executescript(_SEED_PATH.read_text(encoding="utf-8"))
        finally:
            conn.close()


def health() -> dict:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT count(*) AS n FROM user_sessions "
            "WHERE revoked_at IS NULL AND expires_at > CURRENT_TIMESTAMP"
        ).fetchone()
    except sqlite3.OperationalError:
        row = {"n": 0}
    else:
        row = {"n": row["n"]} if row else {"n": 0}
    finally:
        conn.close()
    return {
        "estado": "ok",
        "version_esquema": SCHEMA_VERSION,
        "motor": "sqlite",
        "sesiones_activas": row["n"],
        "archivo": settings.sqlite_path.name,
    }
