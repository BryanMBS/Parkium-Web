"""Migración multi-tenant (Fase 1) — idempotente y sin pérdida de datos.

Uso:
    python scripts/migrate_multi_tenant.py                # base del config
    python scripts/migrate_multi_tenant.py --db ruta.db   # base explícita

Qué hace (copia de seguridad previa + UNA transacción):
 1. Copia el .db a `<nombre>.pre-tenant.bak` (si aún no existe).
 2. Crea la tabla `tenants` y el rol `PLATFORM_ADMIN` (id 4).
 3. Agrega `tenant_id` (FK a tenants + índice) a las tablas raíz del plan
    (Paso 0): users, parking_sites, customers, parking_stays, payments,
    cash_shifts, receipts, tariff_plans, receipt_templates, audit_logs.
 4. Reconstruye `vehicles` con UNIQUE (tenant_id, plate): SQLite no puede
    soltar el UNIQUE global de `plate` con ALTER; se copia fila a fila dentro
    de la misma transacción, sin modificar los datos.
 5. Si NO existen tenants: siembra «Parkaderos Demo S.A.S.» (NIT 900123456-7,
    plan BASIC, límites 2 sedes / 5 usuarios, corte día 1) y asigna TODAS las
    filas existentes a él.
 6. Verificación de conteos por tabla antes/después.

Sobre NOT NULL: SQLite no permite agregar una columna NOT NULL por ALTER; el
`schema.sql` para bases frescas SÍ lo declara y la revisión de Postgres lo
aplicará. En desarrollo queda garantizado a nivel de aplicación.
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

TABLAS = ("users", "parking_sites", "customers", "parking_stays", "payments",
          "cash_shifts", "receipts", "tariff_plans", "receipt_templates",
          "subscriptions", "audit_logs")

TENANT_DEMO = {
    "name": "Parkaderos Demo S.A.S.",
    "nit": "900123456-7",
    "plan": "BASIC",
    "max_sites": 2,
    "max_users": 5,
    "billing_cutoff_day": 1,
}

TENANTS_DDL = (
    """CREATE TABLE IF NOT EXISTS tenants (
        id                 INTEGER PRIMARY KEY,
        name               TEXT NOT NULL,
        nit                TEXT NOT NULL UNIQUE,
        status             TEXT NOT NULL DEFAULT 'ACTIVE',
        plan               TEXT NOT NULL DEFAULT 'BASIC',
        max_sites          INTEGER NOT NULL DEFAULT 1,
        max_users          INTEGER NOT NULL DEFAULT 5,
        billing_cutoff_day INTEGER NOT NULL DEFAULT 1,
        created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
)

VEHICLES_DDL_NUEVA = """
CREATE TABLE vehicles (
    id              INTEGER PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
    plate           TEXT NOT NULL,
    vehicle_type_id INTEGER NOT NULL REFERENCES vehicle_types(id),
    customer_id     INTEGER REFERENCES customers(id),
    brand           TEXT,
    model           TEXT,
    color           TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, plate)
)"""


def _columnas(conn: sqlite3.Connection, tabla: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({tabla})").fetchall()]


def _crear_backup(ruta: Path) -> None:
    if ruta.exists():
        destino = ruta.with_name(ruta.stem + ".pre-tenant.bak")
        if not destino.exists():
            shutil.copy2(ruta, destino)
            print(f"  backup creado: {destino}")


def _agregar_tenant_id(conn: sqlite3.Connection, tabla: str) -> None:
    if "tenant_id" in _columnas(conn, tabla):
        return
    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)")
    conn.execute(f"CREATE INDEX IF NOT EXISTS ix_{tabla}_tenant ON {tabla} (tenant_id)")
    print(f"  + tenant_id y índice -> {tabla}")


def _reconstruir_vehicles(conn: sqlite3.Connection) -> None:
    """vehicles: UNIQUE(plate) global → UNIQUE(tenant_id, plate).

    Con foreign_key_check al final del script (integridad verificada fila a
    fila antes del COMMIT); la app reactiva las FK en cada conexión.
    """
    if "tenant_id" in _columnas(conn, "vehicles"):
        return  # ya migrada (idempotencia)
    print("  reconstruyendo vehicles (UNIQUE pasa a ser por tenant)…")
    conn.execute("DROP TABLE IF EXISTS vehicles_new")
    conn.execute(VEHICLES_DDL_NUEVA.replace("CREATE TABLE vehicles",
                                            "CREATE TABLE vehicles_new"))
    conn.execute("""
        INSERT INTO vehicles_new (id, tenant_id, plate, vehicle_type_id, customer_id,
                                  brand, model, color, notes, created_at)
        SELECT v.id, 1, v.plate, v.vehicle_type_id, v.customer_id,
               v.brand, v.model, v.color, v.notes, v.created_at
        FROM vehicles v""")
    conn.execute("DROP TABLE vehicles")
    conn.execute("ALTER TABLE vehicles_new RENAME TO vehicles")
    conn.execute("DROP INDEX IF EXISTS ix_vehicles_plate")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_vehicles_tenant_plate "
                 "ON vehicles (tenant_id, plate)")


def _contar(conn: sqlite3.Connection, tablas) -> dict[str, int]:
    return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in tablas}


def _sembrar_y_asignar(conn: sqlite3.Connection, tenant_id: int) -> None:
    """Si no hay tenants, crea el demo; asigna a él todo lo que esté sin tenant."""
    hay = conn.execute("SELECT count(*) AS n FROM tenants").fetchone()["n"]
    if hay:
        print(f"  tenants existentes: {hay} (siembra omitida, idempotencia)")
    else:
        conn.execute(
            "INSERT INTO tenants (id, name, nit, status, plan, max_sites, max_users, "
            "billing_cutoff_day) VALUES (?,?,?,?,?,?,?,?)",
            (tenant_id, TENANT_DEMO["name"], TENANT_DEMO["nit"], "ACTIVE",
             TENANT_DEMO["plan"], TENANT_DEMO["max_sites"], TENANT_DEMO["max_users"],
             TENANT_DEMO["billing_cutoff_day"]))
        print(f"  tenant demo creado: {TENANT_DEMO['name']} (id {tenant_id})")
    for tabla in TABLAS:
        conn.execute(f"UPDATE {tabla} SET tenant_id = ? WHERE tenant_id IS NULL", (tenant_id,))
    print("  filas sin tenant reasignadas (si las hubo)")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Migración multi-tenant de Parkium Web.")
    parser.add_argument("--db", default=None, help="Ruta del .db (por defecto, el del config).")
    args = parser.parse_args(argv)

    ruta = Path(args.db) if args.db else config.settings.sqlite_path
    print(f"Migrando {ruta} …")
    _crear_backup(ruta)

    conn = sqlite3.connect(str(ruta), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # FK fuera de la transacción: el reconstruir vehicles hace DROP+RENAME y
    # SQLite no permite alternar el PRAGMA dentro de la transacción. Al final
    # se verifica la integridad completa con foreign_key_check (más estricto:
    # revisa TODAS las filas). La app vuelve a activarlas en cada _connect.
    conn.execute("PRAGMA foreign_keys = OFF")
    tablas_contadas = TABLAS + ("vehicles",)
    antes = _contar(conn, tablas_contadas)
    print("  conteos previos:", antes)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for ddl in TENANTS_DDL:
            conn.execute(ddl)
        conn.execute("""INSERT OR IGNORE INTO roles (id, code, name, description)
                        VALUES (4, 'PLATFORM_ADMIN', 'Administrador de plataforma',
                                'Gestiona clientes (tenants) de toda la plataforma.')""")
        for tabla in TABLAS:
            _agregar_tenant_id(conn, tabla)
        # contraseña temporal de plataforma (Fase 2): fuerza cambio en el primer login
        if "must_change_password" not in _columnas(conn, "users"):
            conn.execute("ALTER TABLE users ADD COLUMN must_change_password "
                         "INTEGER NOT NULL DEFAULT 0")
            print("  + must_change_password -> users")
        _sembrar_y_asignar(conn, tenant_id=1)   # tenants primero: FK del vehicles nuevo
        _reconstruir_vehicles(conn)
        despues = _contar(conn, tablas_contadas)
        perdidas = {t: (antes[t], despues[t], "¡FALTA!")
                    for t in antes if despues[t] < antes[t]}
        tenants_n = conn.execute("SELECT count(*) AS n FROM tenants").fetchone()["n"]
        if perdidas:
            conn.execute("ROLLBACK")
            print("FALLO: filas faltantes ->", perdidas, "(transacción revertida)")
            return 1
        violaciones = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violaciones:
            for v in violaciones[:10]:
                print("FK violada:", dict(v))
            conn.execute("ROLLBACK")
            print("FALLO: integridad referencial violada (transacción revertida)")
            return 1
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    print("  conteos después:", despues, "| tenants:", tenants_n)
    print("Migración multi-tenant completada sin pérdida de filas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
