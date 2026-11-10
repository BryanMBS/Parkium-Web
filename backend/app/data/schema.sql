-- Parkium Web — esquema de desarrollo (SQLite).
-- Referencia de contenido: docs/03-esquema-base-datos.md
-- (25 tablas, índices y seeds). Para producción se migra a PostgreSQL
-- con TIMESTAMPTZ y las restricciones CHECK de docs/03 §3.9.

PRAGMA foreign_keys = ON;

-- ─────────────────────────── 3.2 Acceso ───────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    id          INTEGER PRIMARY KEY,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- raíz del aislamiento multi-tenant (Fase 1)
CREATE TABLE IF NOT EXISTS tenants (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL,
    nit                TEXT NOT NULL UNIQUE,
    status             TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','SUSPENDED')),
    plan               TEXT NOT NULL DEFAULT 'BASIC' CHECK (plan IN ('BASIC','PRO','ENTERPRISE')),
    max_sites          INTEGER NOT NULL DEFAULT 1,
    max_users          INTEGER NOT NULL DEFAULT 5,
    billing_cutoff_day INTEGER NOT NULL DEFAULT 1 CHECK (billing_cutoff_day BETWEEN 1 AND 28),
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    tenant_id     INTEGER REFERENCES tenants(id),  -- NULL sólo para PLATFORM_ADMIN
    username      TEXT NOT NULL UNIQUE,            -- global: evita ambigüedad en el login
    password_hash TEXT NOT NULL,
    full_name     TEXT NOT NULL,
    must_change_password INTEGER NOT NULL DEFAULT 0,  -- contraseña temporal plataforma
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_users_tenant ON users (tenant_id);

CREATE TABLE IF NOT EXISTS user_sessions (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_active ON user_sessions (token_hash, expires_at, revoked_at);

-- ─────────────────────── 3.3 Datos maestros ───────────────────────
CREATE TABLE IF NOT EXISTS parking_sites (
    id             INTEGER PRIMARY KEY,
    tenant_id      INTEGER NOT NULL REFERENCES tenants(id),
    name           TEXT NOT NULL,
    tax_id         TEXT,
    address        TEXT,
    phone          TEXT,
    total_capacity INTEGER NOT NULL DEFAULT 0,
    timezone       TEXT NOT NULL DEFAULT 'America/Bogota',
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_sites_tenant ON parking_sites (tenant_id);
CREATE INDEX IF NOT EXISTS ix_sites_active ON parking_sites (is_active);

CREATE TABLE IF NOT EXISTS parking_zones (
    id         INTEGER PRIMARY KEY,
    site_id    INTEGER NOT NULL REFERENCES parking_sites(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (site_id, name)
);

CREATE TABLE IF NOT EXISTS parking_spaces (
    id              INTEGER PRIMARY KEY,
    zone_id         INTEGER NOT NULL REFERENCES parking_zones(id) ON DELETE CASCADE,
    code            TEXT NOT NULL,
    vehicle_type_id INTEGER NOT NULL REFERENCES vehicle_types(id),
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE (zone_id, code)
);

CREATE TABLE IF NOT EXISTS vehicle_types (
    id         INTEGER PRIMARY KEY,
    code       TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    is_active  INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id              INTEGER PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
    document_type   TEXT,
    document_number TEXT,
    full_name       TEXT NOT NULL,
    email           TEXT,
    phone           TEXT,
    address         TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (tenant_id, document_type, document_number)
);
CREATE INDEX IF NOT EXISTS ix_customers_tenant ON customers (tenant_id);

CREATE TABLE IF NOT EXISTS vehicles (
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
);
CREATE INDEX IF NOT EXISTS ix_vehicles_tenant_plate ON vehicles (tenant_id, plate);

-- ───────────────────────── 3.4 Operación ──────────────────────────
CREATE TABLE IF NOT EXISTS tariff_plans (
    id                 INTEGER PRIMARY KEY,
    site_id            INTEGER NOT NULL REFERENCES parking_sites(id),
    tenant_id          INTEGER NOT NULL REFERENCES tenants(id),
    vehicle_type_id    INTEGER NOT NULL REFERENCES vehicle_types(id),
    name               TEXT NOT NULL,
    billing_scheme     TEXT NOT NULL,
    valid_from         TEXT NOT NULL,
    valid_until        TEXT,
    is_active          INTEGER NOT NULL DEFAULT 1,
    created_by_user_id INTEGER REFERENCES users(id),
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_tariff_lookup ON tariff_plans (site_id, vehicle_type_id, valid_from, valid_until);

CREATE TABLE IF NOT EXISTS tariff_rules (
    id             INTEGER PRIMARY KEY,
    tariff_plan_id INTEGER NOT NULL REFERENCES tariff_plans(id) ON DELETE CASCADE,
    sequence_no    INTEGER NOT NULL DEFAULT 1,
    start_minute   INTEGER NOT NULL DEFAULT 0,
    end_minute     INTEGER,
    amount         NUMERIC NOT NULL,
    grace_minutes  INTEGER NOT NULL DEFAULT 0,
    fraction_minutes INTEGER,
    UNIQUE (tariff_plan_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS parking_stays (
    id               INTEGER PRIMARY KEY,
    site_id          INTEGER NOT NULL REFERENCES parking_sites(id),
    tenant_id        INTEGER NOT NULL REFERENCES tenants(id),
    vehicle_id       INTEGER NOT NULL REFERENCES vehicles(id),
    space_id         INTEGER REFERENCES parking_spaces(id),
    entry_at         TEXT NOT NULL,
    exit_at          TEXT,
    entry_user_id    INTEGER NOT NULL REFERENCES users(id),
    exit_user_id     INTEGER REFERENCES users(id),
    tariff_plan_id   INTEGER REFERENCES tariff_plans(id),
    agreement_id     INTEGER REFERENCES agreements(id),
    entry_photo_path TEXT,
    exit_photo_path  TEXT,
    calculated_amount NUMERIC,
    entry_monotonic  REAL,
    entry_boot_id    TEXT,
    status           TEXT NOT NULL DEFAULT 'ACTIVE',
    notes            TEXT,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_stays_site_entry ON parking_stays (site_id, entry_at);
CREATE INDEX IF NOT EXISTS ix_stays_tenant ON parking_stays (tenant_id);
CREATE INDEX IF NOT EXISTS ix_stays_active_vehicle ON parking_stays (vehicle_id, status);
CREATE INDEX IF NOT EXISTS ix_stays_space_status ON parking_stays (space_id, status);
CREATE TABLE IF NOT EXISTS agreements (
    id             INTEGER PRIMARY KEY,
    site_id        INTEGER NOT NULL REFERENCES parking_sites(id),
    customer_id    INTEGER REFERENCES customers(id),
    name           TEXT NOT NULL,
    discount_type  TEXT NOT NULL,
    discount_value NUMERIC NOT NULL DEFAULT 0,
    valid_from     TEXT NOT NULL,
    valid_until    TEXT,
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payment_methods (
    id        INTEGER PRIMARY KEY,
    code      TEXT NOT NULL UNIQUE,
    name      TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments (
    id                 INTEGER PRIMARY KEY,
    tenant_id          INTEGER NOT NULL REFERENCES tenants(id),
    stay_id            INTEGER REFERENCES parking_stays(id),
    subscription_id    INTEGER REFERENCES subscriptions(id),
    cash_shift_id      INTEGER REFERENCES cash_shifts(id),
    payment_method_id  INTEGER NOT NULL REFERENCES payment_methods(id),
    received_by_user_id INTEGER NOT NULL REFERENCES users(id),
    amount             NUMERIC NOT NULL,
    amount_received    NUMERIC,
    change_amount      NUMERIC,
    paid_at            TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    external_reference TEXT,
    idempotency_key    TEXT UNIQUE,
    status             TEXT NOT NULL DEFAULT 'APPROVED',
    voided_by_user_id  INTEGER REFERENCES users(id),
    voided_at          TEXT,
    void_reason        TEXT
);
CREATE INDEX IF NOT EXISTS ix_payments_tenant ON payments (tenant_id);
CREATE INDEX IF NOT EXISTS ix_payments_shift ON payments (cash_shift_id, status);
CREATE INDEX IF NOT EXISTS ix_payments_paid_at ON payments (paid_at);

CREATE TABLE IF NOT EXISTS cash_shifts (
    id                INTEGER PRIMARY KEY,
    site_id           INTEGER NOT NULL REFERENCES parking_sites(id),
    tenant_id         INTEGER NOT NULL REFERENCES tenants(id),
    user_id           INTEGER NOT NULL REFERENCES users(id),
    opened_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at         TEXT,
    opening_amount    NUMERIC NOT NULL DEFAULT 0,
    expected_amount   NUMERIC,
    counted_amount    NUMERIC,
    difference_amount NUMERIC,
    status            TEXT NOT NULL DEFAULT 'OPEN',
    notes             TEXT,
    UNIQUE (site_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_shifts_tenant ON cash_shifts (tenant_id);
CREATE INDEX IF NOT EXISTS ix_shifts_open ON cash_shifts (site_id, user_id, status);

-- ──────────────────── 3.5 Mensualidades ──────────────────────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id              INTEGER PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES parking_sites(id),
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id),
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    plan_name       TEXT NOT NULL,
    starts_on       TEXT NOT NULL,
    expires_on      TEXT NOT NULL,
    amount          NUMERIC NOT NULL,
    permitted_start TEXT,
    permitted_end   TEXT,
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_subscriptions_expiry ON subscriptions (site_id, expires_on, status);

CREATE TABLE IF NOT EXISTS subscription_vehicles (
    subscription_id INTEGER NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
    vehicle_id      INTEGER NOT NULL REFERENCES vehicles(id),
    PRIMARY KEY (subscription_id, vehicle_id)
);

-- ───────────────── 3.6 Comprobantes ───────────────────────────────
CREATE TABLE IF NOT EXISTS receipts (
    id             INTEGER PRIMARY KEY,
    site_id        INTEGER NOT NULL REFERENCES parking_sites(id),
    tenant_id      INTEGER NOT NULL REFERENCES tenants(id),
    payment_id     INTEGER REFERENCES payments(id),
    stay_id        INTEGER REFERENCES parking_stays(id),
    receipt_number INTEGER NOT NULL,
    receipt_type   TEXT NOT NULL,
    issued_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    qr_payload     TEXT,
    reprint_count  INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'ISSUED',
    UNIQUE (site_id, receipt_number)
);

CREATE TABLE IF NOT EXISTS receipt_counters (
    site_id     INTEGER PRIMARY KEY REFERENCES parking_sites(id) ON DELETE CASCADE,
    next_number INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS receipt_templates (
    id                INTEGER PRIMARY KEY,
    site_id           INTEGER NOT NULL REFERENCES parking_sites(id) ON DELETE CASCADE,
    tenant_id         INTEGER NOT NULL REFERENCES tenants(id),
    template_name     TEXT NOT NULL DEFAULT 'Plantilla predeterminada',
    parking_name      TEXT NOT NULL DEFAULT 'PARKIUM',
    nit               TEXT,
    address           TEXT,
    header_text       TEXT,
    terms_text        TEXT,
    footer_text       TEXT DEFAULT 'PARKIUM - Todos los derechos reservados.',
    show_barcode      INTEGER NOT NULL DEFAULT 1,
    show_qr           INTEGER NOT NULL DEFAULT 1,
    is_active         INTEGER NOT NULL DEFAULT 1,
    updated_by_user_id INTEGER REFERENCES users(id),
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (site_id, template_name)
);
CREATE INDEX IF NOT EXISTS ix_receipt_templates_site ON receipt_templates (site_id, is_active);

CREATE TABLE IF NOT EXISTS electronic_invoices (
    id               INTEGER PRIMARY KEY,
    receipt_id       INTEGER NOT NULL REFERENCES receipts(id),
    provider         TEXT NOT NULL,
    external_id      TEXT,
    cufe             TEXT,
    qr_payload       TEXT,
    status           TEXT NOT NULL,
    request_payload  TEXT,
    response_payload TEXT,
    error_message    TEXT,
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, receipt_id)
);
CREATE INDEX IF NOT EXISTS ix_electronic_receipt ON electronic_invoices (receipt_id);

-- ──────────── 3.7 Seguridad del reloj y auditoría ─────────────────
CREATE TABLE IF NOT EXISTS clock_anchors (
    id                INTEGER PRIMARY KEY,
    boot_id           TEXT,
    boot_utc          TEXT,
    boot_monotonic    REAL,
    last_trusted_utc  TEXT,
    max_drift_seconds REAL
);

CREATE TABLE IF NOT EXISTS clock_checks (
    id             INTEGER PRIMARY KEY,
    checked_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source         TEXT NOT NULL,
    system_utc     TEXT,
    reference_utc  TEXT,
    drift_seconds  REAL,
    is_suspicious  INTEGER NOT NULL DEFAULT 0,
    message        TEXT
);
CREATE INDEX IF NOT EXISTS ix_clock_checks_occurred ON clock_checks (checked_at);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id),
    tenant_id   INTEGER REFERENCES tenants(id),  -- NULL: acción de plataforma
    entity_type TEXT,
    entity_id   INTEGER,
    action      TEXT NOT NULL,
    before_data TEXT,
    after_data  TEXT,
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address  TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_occurred ON audit_logs (occurred_at);
CREATE INDEX IF NOT EXISTS ix_audit_tenant ON audit_logs (tenant_id, occurred_at);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_logs (entity_type, entity_id);

-- ─────────────────── 3.8 Datos iniciales ──────────────────────────
-- (En backend/app/data/seed.sql — idempotente, docs/09 tarea 1.5)
