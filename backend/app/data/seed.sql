-- Seeds de Parkium Web (docs/03 §3.8) — idempotentes, se pueden correr dos veces.
INSERT OR IGNORE INTO roles (id, code, name, description) VALUES
  (1, 'ADMIN', 'Administrador',
      'Configuración operativa, usuarios y caja. Sin reportes ni datos fiscales.'),
  (2, 'OPERATOR', 'Operador',
      'Registra entradas, salidas, cobros y su caja.'),
  (3, 'SUPERADMIN', 'Super administrador',
      'Acceso total: datos del parqueadero, plantillas, reportes y usuarios.'),
  (4, 'PLATFORM_ADMIN', 'Administrador de plataforma',
      'Gestiona clientes (tenants) de toda la plataforma. tenant_id NULL.');
-- Tenant raíz para instalaciones frescas (el mismo de la migración multi-tenant).
INSERT OR IGNORE INTO tenants (id, name, nit, status, plan, max_sites, max_users, billing_cutoff_day)
  VALUES (1, 'Parkaderos Demo S.A.S.', '900123456-7', 'ACTIVE', 'BASIC', 2, 5, 1);

INSERT OR IGNORE INTO vehicle_types (id, code, name) VALUES
  (1, 'CAR', 'Carro'), (2, 'MOTORCYCLE', 'Moto'), (3, 'BICYCLE', 'Bicicleta');

INSERT OR IGNORE INTO payment_methods (id, code, name) VALUES
  (1, 'CASH', 'Efectivo'), (2, 'CARD', 'Tarjeta'),
  (3, 'TRANSFER', 'Transferencia'), (4, 'DIGITAL_WALLET', 'Billetera digital');

INSERT OR IGNORE INTO parking_sites (id, name, total_capacity, timezone, is_active)
  VALUES (1, 'Parkium - Sede temporal', 30, 'America/Bogota', 1);

INSERT OR IGNORE INTO receipt_counters (site_id, next_number)
  SELECT 1, 1 WHERE NOT EXISTS (SELECT 1 FROM receipt_counters WHERE site_id = 1);

INSERT OR IGNORE INTO receipt_templates
  (id, site_id, template_name, parking_name, footer_text)
  VALUES (1, 1, 'Plantilla predeterminada', 'PARKIUM', 'PARKIUM - Todos los derechos reservados.');

-- Semillas de tarifas de ejemplo (una por tipo de vehículo, esquema HOUR).
INSERT OR IGNORE INTO tariff_plans (id, site_id, vehicle_type_id, name, billing_scheme, valid_from, valid_until, is_active)
  VALUES (1, 1, 1, 'Hora carro', 'HOUR', '2024-01-01T00:00:00+00:00', NULL, 1),
         (2, 1, 2, 'Hora moto', 'HOUR', '2024-01-01T00:00:00+00:00', NULL, 1),
         (3, 1, 3, 'Hora bicicleta', 'HOUR', '2024-01-01T00:00:00+00:00', NULL, 1);

INSERT OR IGNORE INTO tariff_rules (id, tariff_plan_id, sequence_no, start_minute, end_minute, amount, grace_minutes)
  VALUES (1, 1, 1, 0, NULL, 5000.00, 5),
         (2, 2, 1, 0, NULL, 3000.00, 5),
         (3, 3, 1, 0, NULL, 2000.00, 5);
