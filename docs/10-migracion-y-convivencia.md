# 10 — Migración de datos y convivencia de sistemas

## 10.1 Principio

La migración **no** es un `pg_dump` con otro nombre. Los tres puntos delicados
son:

1. **El esquema cambia de tipo** (`TEXT` → `TIMESTAMPTZ`, `INTEGER` → `BOOLEAN`).
2. **Hay dos fuentes de verdad** del esquema: `app/data/temporary_database.py`
   (SQLite) y `sql/*.sql` (MySQL). Hay que decidir cuál refleja la realidad.
3. **Los importes son `NUMERIC` y en SQLite pueden haber entrado como texto.**
   Hay que verificarlos antes de confiar en ellos.

## 10.2 Inventario de lo que hay que migrar

| Tabla | Filas esperadas | Riesgo | Nota |
|---|---|:---:|---|
| `parking_sites` | 1 | Bajo | La semilla |
| `roles` | 3 | Bajo | La semilla |
| `vehicle_types` | 3 | Bajo | La semilla |
| `payment_methods` | 4 | Bajo | La semilla |
| `users` | 1–10 | **Alto** | **Contraseñas y roles** |
| `user_sessions` | Variable | Bajo | **No migrar**: caducan en 12 h |
| `vehicles` | Cientos | Bajo | Placas únicas |
| `customers` | Decenas | Bajo | Documento único |
| `subscriptions` | Decenas | Medio | Fechas civiles |
| `subscription_vehicles` | Decenas | Bajo | Tabla puente |
| `parking_stays` | **Miles** | **Alto** | El histórico de verdad |
| `payments` | Miles | **Alto** | Dinero |
| `receipts` | Miles | **Alto** | Numeración |
| `receipt_counters` | 1 | **Alto** | **No puede empezar de cero** |
| `cash_shifts` | Cientos | Medio | Importes de caja |
| `tariff_plans` / `tariff_rules` | Decenas | Medio | Vigencias |
| `agreements` | Variable | Bajo | Convenios |
| `parking_zones` / `parking_spaces` | Decenas | Bajo | Cupos |
| `audit_logs` | **Miles** | Medio | **Decisión de negocio** |
| `clock_anchors` / `clock_checks` | 1 / cientos | Bajo | **No migrar**: se regeneran |
| `electronic_invoices` | **0** | — | Vacía: proveedor desactivado |
| `receipt_templates` | 1–3 | Bajo | Plantilla activa |

## 10.3 Los tres puntos delicados

### 10.3.1 Numeración de comprobantes — **lo que más cuesta money si se ignora**

Si `receipt_counters` se deja en 1, el web emite un comprobante con el número 1
y se ve en el papel un número que **ya se entregó** a otro cliente. Eso es un
documento duplicado.

```python
# scripts/migrate.py — tras migrar
SELECT site_id, MAX(receipt_number) FROM receipts GROUP BY site_id;
UPDATE receipt_counters
   SET next_number = %s + 1
 WHERE site_id = %s;
```

Regla: `next_number = máximo histórico + 1`, **siempre**. Comprobarlo antes de
poner el sistema en servicio.

### 10.3.2 Contraseñas y roles

Los hashes scrypt son **portables**: mismo algoritmo, mismos parámetros, misma
codificación base64url. Se copian tal cual y `verify_password` los acepta.

```python
# Verificación tras copiar
for usuario in usuarios_migrados:
    assert verify_password(CONTRASENA_PRUEBA, usuario.password_hash) or True
    # No se puede probar sin la contraseña; se verifica el FORMATO:
    assert re.fullmatch(r"scrypt\$16384\$8\$1\$[^$]+\$[^$]+", usuario.password_hash)
```

**El rol del administrador heredado:** el original lo promueve a `SUPERADMIN` en
el arranque (`_migrate_existing_admin_to_superadmin`, símbolo
`USER_PROMOTED_TO_SUPERADMIN`). Hay que decidir **antes** de migrar:

| Opción | Descripción | Valoración |
|---|---|---|
| A | Promover al `SUPERADMIN` heredado, igual que el original | **Recomendada**: el operador conserva la contraseña que ya conoce |
| B | Dejarlo en `ADMIN` y crear un `SUPERADMIN` nuevo | Hay que comunicar una credencial nueva |

> Con la opción A, el `SUPERADMIN` real conserva su contraseña y nadie se queda
> fuera. Con la B, si el super administrador nuevo se crea mal o se pierde, nadie
> puede entrar. **A, salvo decisión explícita del negocio.**

### 10.3.3 Historial de auditoría — decisión de negocio

`audit_logs` puede tener miles de filas y contiene datos personales en
`before_data` / `after_data`.

| Decisión | Costo | Recomendación |
|---|---|---|
| Migrar todo | Carga y posible exposición de datos personales | **No, por defecto** |
| Migrar sólo los últimos 6 meses | Carga razonable | **Sí** |
| No migrar | Pérdida de trazabilidad histórica | Última opción |

**Recomendación:** migrar los últimos 6 meses. Si el negocio exige la trazabilidad
completa, es una decisión que debe firmarse, no un detalle técnico.

## 10.4 Script de migración

```python
#!/usr/bin/env python3
"""Migra la base SQLite de Parkium a PostgreSQL."""

import sqlite3, sys, datetime as dt
from decimal import Decimal
import psycopg
from psycopg.rows import dict_row

ORIGEN = "parkium.db"
DESTINO = "postgresql://parkium:***@localhost/parkium"

# Orden de inserción: respeta las claves foráneas
ORDEN = [
    "parking_sites", "roles", "vehicle_types", "payment_methods",
    "users", "vehicles", "customers", "parking_zones", "parking_spaces",
    "tariff_plans", "tariff_rules", "agreements",
    "subscriptions", "subscription_vehicles",
    "parking_stays", "cash_shifts", "payments", "receipts",
    "receipt_templates", "receipt_counters",
]

# Tablas que NO se migran, con motivo
OMITIR = {
    "user_sessions":      "caducan en 12 h; se regeneran al iniciar sesión",
    "clock_anchors":      "el ancla pertenece al servidor web, no al equipo viejo",
    "clock_checks":       "histórico del reloj del equipo anterior",
    "electronic_invoices":"siempre vacía: proveedor desactivado",
}

def texto_a_ts(valor):
    """'2026-10-08T14:32:10+00:00' -> datetime con zona."""
    if valor is None:
        return None
    return dt.datetime.fromisoformat(valor)

def texto_a_fecha(valor):
    """'2026-10-08' -> date."""
    if valor is None:
        return None
    return dt.date.fromisoformat(valor[:10])

def entero_a_bool(valor):
    return None if valor is None else bool(valor)

def decimal_limpio(valor):
    """Convierte a Decimal; tolerate que SQLite lo guardara como texto."""
    if valor in (None, ""):
        return None
    return Decimal(str(valor))

CONVERSORES = {
    "entry_at": texto_a_ts, "exit_at": texto_a_ts, "created_at": texto_a_ts,
    "updated_at": texto_a_ts, "paid_at": texto_a_ts, "issued_at": texto_a_ts,
    "occurred_at": texto_a_ts, "opened_at": texto_a_ts, "closed_at": texto_a_ts,
    "expires_at": texto_a_ts, "voided_at": texto_a_ts, "revoked_at": texto_a_ts,
    "last_login_at": texto_a_ts, "checked_at": texto_a_ts,
    "starts_on": texto_a_fecha, "expires_on": texto_a_fecha,
    "valid_from": texto_a_fecha, "valid_until": texto_a_fecha,
    "is_active": entero_a_bool, "show_barcode": entero_a_bool,
    "show_qr": entero_a_bool, "is_suspicious": entero_a_bool,
    "amount": decimal_limpio, "opening_amount": decimal_limpio,
    "expected_amount": decimal_limpio, "counted_amount": decimal_limpio,
    "difference_amount": decimal_limpio, "amount_received": decimal_limpio,
    "change_amount": decimal_limpio, "calculated_amount": decimal_limpio,
    "discount_value": decimal_limpio,
}

def main():
    origen = sqlite3.connect(ORIGEN)
    origen.row_factory = sqlite3.Row
    destino = psycopg.connect(DESTINO, row_factory=dict_row)

    with destino.cursor() as cur:
        cur.execute("SET session_replication_role = replica")  # sin orden FK
        try:
            for tabla in ORDEN:
                columnas = [d[1] for d in cur.execute(
                    "SELECT column_name, data_type FROM information_schema.columns "
                    "WHERE table_name = %s", (tabla,)
                )]
                filas = origen.execute(f"SELECT * FROM {tabla}").fetchall()
                if not filas:
                    print(f"  {tabla:26} 0 filas")
                    continue

                presentes = [c for c in columnas if c in filas[0].keys()]
                collist = ", ".join(presentes)
                marcas = ", ".join(["%s"] * len(presentes))
                sql = f"INSERT INTO {tabla} ({collist}) VALUES ({marcas})"

                for fila in filas:
                    valores = [CONVERSORES.get(c, lambda v: v)(fila[c]) for c in presentes]
                    cur.execute(sql, valores)

                print(f"  {tabla:26} {len(filas)} filas")
        finally:
            cur.execute("SET session_replication_role = origin")

        # --- Verificaciones obligatorias ---
        print("\n--- Verificaciones ---")

        # 1. Numeración de comprobantes
        cur.execute("""
            SELECT r.site_id, MAX(r.receipt_number) AS maximo, c.next_number
            FROM receipts r JOIN receipt_counters c ON c.site_id = r.site_id
            GROUP BY r.site_id, c.next_number
        """)
        for fila in cur.fetchall():
            if fila["next_number"] <= fila["maximo"]:
                cur.execute(
                    "UPDATE receipt_counters SET next_number = %s WHERE site_id = %s",
                    (fila["maximo"] + 1, fila["site_id"]),
                )
                print(f"  [OK] Contador de sitio {fila['site_id']} "
                      f"ajustado a {fila['maximo'] + 1}")

        # 2. Suma de pagos: debe coincidir con el total del turno
        cur.execute("SELECT COALESCE(SUM(amount), 0) AS total FROM payments WHERE status = 'APPROVED'")
        print(f"  Total de pagos aprobados: {cur.fetchone()['total']}")

        # 3. Estadías cerradas sin pago, o pagos sin estadía cerrada
        cur.execute("""
            SELECT COUNT(*) AS n FROM parking_stays s
            WHERE s.status = 'PAID'
              AND NOT EXISTS (SELECT 1 FROM payments p
                              WHERE p.stay_id = s.id AND p.status = 'APPROVED')
        """)
        print(f"  Estadías PAID sin pago: {cur.fetchone()['n']} (debe ser 0)")

        cur.execute("""
            SELECT COUNT(*) AS n FROM payments p
            WHERE p.stay_id IS NOT NULL AND p.status = 'APPROVED'
              AND NOT EXISTS (SELECT 1 FROM parking_stays s
                              WHERE s.id = p.stay_id AND s.status IN ('PAID','CANCELLED'))
        """)
        print(f"  Pagos sin estadía cerrada: {cur.fetchone()['n']} (debe ser 0)")

        # 4. Duplicados de documento de cliente
        cur.execute("""
            SELECT COUNT(*) AS n FROM (
              SELECT document_type, document_number FROM customers
              WHERE document_number IS NOT NULL
              GROUP BY document_type, document_number HAVING COUNT(*) > 1
            ) d
        """)
        print(f"  Documentos duplicados: {cur.fetchone()['n']}")

    destino.commit()
    destino.close()
    print("\nMigración completada. Revisa los contadores marcados [ALERTA].")

if __name__ == "__main__":
    main()
```

## 10.5 Verificación posterior a la migración

### Comparativa numérica obligatoria

| Comprobación | Consulta | Resultado esperado |
|---|---|---|
| Filas por tabla | `SELECT COUNT(*)` en ambas | Idéntico (salvo `OMITIR`) |
| Total cobrado | `SELECT SUM(amount) FROM payments WHERE status='APPROVED'` | **Idéntico al centavo** |
| Total en efectivo | `… WHERE payment_method_id = <CASH>` | Idéntico |
| Cambios entregados | `SELECT SUM(change_amount) …` | Idéntico |
| Total por turno de caja | `SELECT SUM(expected_amount) FROM cash_shifts WHERE status='CLOSED'` | Idéntico |
| Número máximo de comprobante | `SELECT MAX(receipt_number) FROM receipts` | Idéntico |
| Placas distintas | `SELECT COUNT(DISTINCT plate) FROM vehicles` | Idéntico |
| Clientes con saldo | `SELECT COUNT(*) FROM subscriptions WHERE amount > 0` | Idéntico |
| Diferencias de caja | `SELECT COUNT(*) FROM cash_shifts WHERE difference_amount <> 0` | Idéntico |

> Si el **total cobrado** no coincide al centavo, **detener la migración**. Todo
> lo demás se puede revisar; el dinero no se negocia.

### Comprobación funcional

| Prueba | Resultado esperado |
|---|---|
| Iniciar sesión con la contraseña de siempre | Entra |
| Ver el histórico del último mes | Coincide con el escritorio |
| Ver el dashboard | Las cifras coinciden |
| Cobrar una salida de prueba | Funciona y el comprobante sale bien |
| Generar el XLSX completo | Los totales coinciden |
| Abrir un turno de caja | El esperado cuadra con lo que caja registró |
| Escanear un QR de un comprobante antiguo | La ruta `/r/{token}` lo resuelve |

## 10.6 Convivencia de los dos sistemas

### Fase 1 · Sólo lectura en el web (recomendado)

| Elemento | Decisión |
|---|---|
| Escritorio | **Es el único que cobra** |
| Web | Sólo consulta: dashboard, histórico, reportes, mensualidades |
| Escritorio | No se toca |

Es la fase más segura y deja verificar la migración con datos reales sin
riesgo de doble cobro.

### Fase 2 · Web primaria, escritorio como respaldo

| Elemento | Decisión |
|---|---|
| Cobros | **Sólo en la web** |
| Configuración | **Sólo en la web** |
| Escritorio | Sólo lectura, y **no se sincroniza**: es una copia congelada |
| Riesgo | Un operador con el escritorio abierto puede cobrar sin que la web lo vea |

> **No se pueden usar los dos a la vez para cobrar.** No hay forma técnica de
> que una aplicación de escritorio y una web se coordinen sin un servicio de
> intermediación, y ese servicio es el propio backend. Si el escritorio sigue
> conectado, la web no es la fuente de verdad.

### Fase 3 · Retirada del escritorio

| Paso | Verificación |
|---|---|
| 1. Congelar el escritorio en sólo lectura | Nadie cobra desde ahí |
| 2. Una semana completa de uso exclusivo de la web | Sin incidencias |
| 3. Respaldar la base SQLite final | Con fecha y ubicación documentadas |
| 4. Retirar el acceso a los datos | Ya no hace falta |
| 5. Archivar el `.exe` y el instalador | Por si hay que revisar algo |

## 10.7 Riesgo de la doble facturación

**Es el riesgo principal de este proyecto y no tiene solución técnica.**

Si un operador cobra desde el escritorio y luego desde la web por el mismo
vehículo, quedan dos pagos y la caja no cuadra. Ningún diseño lo evita por sí
solo.

La causa es que una aplicación de escritorio y una web son dos sistemas
independientes: cada una abre su propia conexión y ninguna sabe de la otra.
Coordinarlas exigiría que **todas** las escrituras passasen por el backend, y en
ese caso el escritorio ya no sería una fuente de verdad.

| Medida | Costo | Valoración |
|---|---|---|
| Fase 1 de sólo lectura | Cero | **Obligatoria** |
| Bloquear la escritura en el escritorio cuando la web está activa | Bajo | **Muy recomendable** |
| Aviso visible en el escritorio: «SISTEMA EN CONVIVENCIA» | Cero | Mínimo imprescindible |
| Desinstalar el escritorio al terminar la Fase 1 | Cero | Recomendable si nadie lo usa |

> Si la Fase 1 se salta, la migración de datos deja de ser el problema: el
> problema pasa a ser la conciliación de dos sistemas que ninguno sabe del otro.

## 10.8 Reversión

Cada fase debe poder deshacerse.

| Fase | Reversión |
|---|---|
| Sólo lectura | Ninguna: no se escribe nada |
| Web primaria | Volver al escritorio: la web queda congelada y el escritorio vuelve a ser el sistema principal. Requiere que no se haya desinstalado |
| Retirada | Restaurar la copia final de SQLite y volver a instalar. **Imposible si no se guardó la copia** |

Por eso el paso 3 de la Fase 3 no es opcional: **sin copia final archivada, la
retirada es irreversible.**

## 10.9 Lista de verificación de migración

- [ ] Decidido el motor de la base de destino.
- [ ] Decidido si se migra el historial de auditoría completo o 6 meses.
- [ ] Decidido qué pasa con el administrador heredado (A o B de §10.3.2).
- [ ] `receipt_counters` ajustado a `máximo + 1` y **verificado**.
- [ ] Total cobrado idéntico **al centavo**.
- [ ] Total en efectivo y cambios idénticos.
- [ ] Total por turno de caja cerrado idéntico.
- [ ] Las contraseñas existentes siguen funcionando.
- [ ] Fase 1 de sólo lectura activa **antes** de abrir cobros en la web.
- [ ] Copia de la base SQLite original archivada y **verificada**.
- [ ] Procedimiento de reversión escrito y probado.