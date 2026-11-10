# 04 — Especificación de API

Todas las rutas cuelgan de `/api`. Convenciones globales:

| Aspecto | Regla | Fuente / razón |
|---|---|---|
| **Formato** | JSON UTF-8 | — |
| **Importes** | **Cadena decimal**, nunca número JSON | `Decimal` en todo el dominio; un `float` de JavaScript no representa `$45,000.00` exacto |
| **Fechas** | `YYYY-MM-DD` para fechas civiles; ISO-8601 con zona para marcas de tiempo | `history._parse_day` |
| **Horas** | `hh:mm` en 24 h, siempre | Regla del proyecto |
| **Errores** | `{ "codigo": "…", "mensaje": "…", "detalle": {…} }` | — |
| **Autorización** | Cookie `HttpOnly` + `Secure` + `SameSite=Lax` | Tabla `user_sessions` |
| **Idempotencia** | Cabecera `Idempotency-Key` en cobros | `payments.idempotency_key` UNIQUE |
| **Transacciones** | `BEGIN IMMEDIATE` en todo cobro | `parking_operations.collect_payment` |

## 4.1 Códigos de error

| HTTP | `codigo` | Cuándo |
|---|---|---|
| 400 | `validacion` | Regla de negocio incumplida |
| 400 | `reloj_no_confiable` | `ClockIntegrityError` — **bloquea el cobro** |
| 401 | `no_autenticado` | Sin sesión o sesión expirada |
| 401 | `credenciales` | Usuario o contraseña incorrectos |
| 403 | `sin_permisos` | `AuthorizationError` |
| 403 | `recurso_restringido` | Mensaje de «Acceso restringido» |
| 404 | `no_encontrado` | Entidad inexistente |
| 409 | `conflicto` | Placa con estadía activa, documento duplicado, turno abierto |
| 409 | `idempotencia` | Clave de idempotencia ya usada con otro objetivo |
| 422 | `campos` | Validación de esquema |
| 500 | `interno` | Fallo no previsto (se registra, no se filtra) |
| 503 | `reloj_no_verificable` | La fuente externa no respondió y no hay ancla válida |

---

## 4.2 Autenticación

### `POST /api/auth/login`

```json
// Entrada
{ "usuario": "BSMB", "contraseña": "…" }

// 200
{
  "usuario": { "id": 1, "nombre": "BSMB", "nombre_completo": "Root", "rol": "SUPERADMIN" },
  "expira_en": "2026-10-09T02:14:55+00:00"
}
```

Reglas: scrypt en el servidor; la sesión dura 12 h
(`SESSION_DURATION`); sólo se devuelve `token_hash` (SHA-256) a la base.
Errores: `401 credenciales`, `401 no_autenticado` si el usuario está inactivo.

### `POST /api/auth/logout`

Revoca la sesión actual. `204`.

### `GET /api/auth/me`

```json
{ "id": 1, "usuario": "BSMB", "nombre_completo": "Root", "rol": "SUPERADMIN" }
```

### `POST /api/auth/password`

```json
// Entrada
{ "actual": "…", "nueva": "…" }
```

Valida `PASSWORD_MIN_LENGTH = 10` y máximo 256. `200` con mensaje, `401
credenciales` si la actual no coincide.

### `POST /api/auth/first-user`

Sólo válido si `has_users()` es falso (`app/services/authentication.py:has_users`).
Crea el super administrador de arranque. **Debe quedar cerrado en cuanto exista
un usuario**; ver [12-preguntas-abiertas.md](12-preguntas-abiertas.md) §2.

---

## 4.3 Operación

### `POST /api/stays` — Registrar entrada

```json
// Entrada
{ "placa": "abc123", "tipo_vehiculo": "CAR" }

// 201
{
  "estadia_id": 42,
  "placa": "ABC123",
  "ingreso": "2026-10-08T14:32:10+00:00",
  "ingreso_local": "2026-10-08 09:32",
  "monto_a_cobrar": 5000,
  "mensualidad_vigente": false,
  "recibo": { "id": 88, "numero": 88, "tipo": "ENTRY" }
}
```

Reglas:
- Normaliza la placa a mayúsculas sin espacios (`_normalise_plate`).
- Si no existe el vehículo, **lo crea** (`register_entry`).
- Emite la factura de ingreso en la misma transacción.
- Si ya hay una estadía `ACTIVE` o `PENDING_PAYMENT` para esa placa: `409 conflicto`.

### `GET /api/stays/active?placa=ABC123`

```json
{ "estadia_id": 42, "placa": "ABC123", "ingreso_local": "2026-10-08 09:32", "estado": "ACTIVE" }
```

### `GET /api/stays/{placa}/quote` — Cotizar salida

```json
{
  "estadia_id": 42,
  "placa": "ABC123",
  "entrada_local": "2026-10-08 07:12",
  "salida_local": "2026-10-08 11:40",
  "minutos": 268,
  "esquema": "HOUR",
  "monto": "13500.00",
  "descuento": "0.00",
  "monto_a_cobrar": "13500.00",
  "monto_recibido": null,
  "cambio": null
}
```

**No cierra la estadía.** Calcula con reloj monotónico si la entrada comparte
proceso (`elapsed_minutes`), si no con la hora del sistema ya validada.

### `POST /api/checkout` — Cobrar salida

```json
// Entrada
{
  "placa": "ABC123",
  "metodo": "CASH",
  "monto": "13500.00",
  "efectivo_recibido": "20000.00",
  "referencia": null
}
// Cabecera
Idempotency-Key: 6f1c2e40-…
```

```json
// 200
{
  "pago_id": 501,
  "estadia_id": 42,
  "estado": "PAID",
  "monto": "13500.00",
  "efectivo_recibido": "20000.00",
  "cambio": "6500.00",
  "recibo": { "id": 89, "numero": 89, "tipo": "EXIT" }
}
```

Reglas, **todas transaccionales**:
1. `check_before_billing` — si el reloj no es confiable, `400 reloj_no_confiable`.
2. `monto >= cotización`; si es menor, `400 validacion`.
3. Sólo `CASH` registra `efectivo_recibido` y `cambio`. Para los demás métodos,
   si vienen con un valor distinto al monto: `400 validacion`.
4. Efectivo insuficiente: `400 validacion` con `"Faltan $8.500,00"`.
5. El cobro en efectivo exige turno abierto; si no, `400 validacion`.
6. La misma `Idempotency-Key` devuelve el pago existente en vez de duplicar.

### `POST /api/payments/{id}/void` — Anular cobro

```json
{ "motivo": "Error de saldo" }
```

Devuelve la estadía a `ACTIVE`. Sólo para administradores.

### `GET /api/occupancy` — Ocupación actual

```json
{
  "capacidad_total": 30,
  "ocupados": 6,
  "disponibles": 24,
  "por_tipo": { "CAR": 5, "MOTORCYCLE": 1 }
}
```

---

## 4.4 Comprobantes

### `GET /api/receipts/{id}/preview`

Devuelve el comprobante listo para mostrar antes de imprimir.

```json
{
  "id": 89, "numero": 89, "tipo": "EXIT",
  "parqueadero": { "nombre": "PARKIUM", "nit": "900.123.456-7", "direccion": "…" },
  "lineas": ["PARKIUM", "Recibo de pago", "…"],
  "codigo_barras": "ABC123",
  "url_qr": "https://parkium.ejemplo.com/r/9f2a…",
  "mostrar_codigo_barras": true,
  "mostrar_qr": true
}
```

### `GET /api/receipts/{id}/pdf` · `/image` · `/barcode.png` · `/qr.png`

Devuelven el archivo. `render_receipt_image` produce PNG monocromático de
ticket 58 u 80 mm.

### `GET /api/receipts/{id}/escpos`

Texto ESC/POS listo para enviar a la impresora térmica.

### `POST /api/receipts/{id}/reprint`

```json
{ "tipo": "ENTRY" }
```

Incrementa `reprint_count`, escribe auditoría y valida rol.
Usa `reprint_receipt_for_user`; un documento ya reimprimido N veces queda
identificable por su contador.

### `GET /r/{token}` — Recibo público (fuera de `/api`)

Resuelve el token del QR y muestra el comprobante en HTML.
Equivale a `receipt_web.ReceiptRequestHandler` pero servido por el servidor web.
**Sin autenticación**: es laURL que va impresa en el papel.

### `POST /api/receipts/{id}/print`

Envía a la impresora del sistema. **Sólo disponible si el servidor es Windows**
con `pywin32`. Ver [12-preguntas-abiertas.md](12-preguntas-abiertas.md) §3.

---

## 4.5 Histórico

### `GET /api/history`

| Parámetro | Tipo | Nota |
|---|---|---|
| `placa` | texto | Coincidencia parcial, en mayúsculas |
| `desde` | `YYYY-MM-DD` | Civil local |
| `hasta` | `YYYY-MM-DD` | Civil local, inclusivo |
| `estado` | `ACTIVE\|PENDING_PAYMENT\|PAID\|CANCELLED` | |
| `tipo_vehiculo` | `CAR\|MOTORCYCLE\|BICYCLE` | |
| `limite` | entero | Por defecto 500, máximo 5000 |

```json
{
  "total": 4,
  "resultados": [
    {
      "estadia_id": 42, "placa": "ABC123", "tipo_vehiculo": "Carro", "celda": "A-01",
      "fecha_ingreso": "2026-10-08", "hora_ingreso": "07:12",
      "fecha_salida": "2026-10-08", "hora_salida": "11:40",
      "estado": "Cobrada", "monto": "13500.00",
      "duracion_minutos": 268,
      "recibo_ingreso": { "id": 12, "numero": 12, "puede_reimprimir": true },
      "recibo_salida": { "id": 89, "numero": 89, "puede_reimprimir": true }
    }
  ]
}
```

Sin rango, la búsqueda se limita al día de hoy. Si `desde > hasta`: `400 validacion`.

### `GET /api/occupancy/hourly?fecha=YYYY-MM-DD`

```json
{
  "fecha": "2026-10-08",
  "capacidad_total": 30,
  "puntos": [
    { "hora": 0, "ocupados": 0, "por_tipo": {} },
    { "hora": 9, "ocupados": 4, "por_tipo": { "CAR": 3, "MOTORCYCLE": 1 } }
  ],
  "maximo": 5
}
```

Siempre **24 puntos**, aunque el día esté vacío. Franjas en **hora local del
sitio**: el día local de Bogotá empieza a las 05:00 UTC y construir las franjas
a medianoche UTC desplaza la curva cinco horas.

### `GET /api/occupancy/detail?fecha=YYYY-MM-DD&hora=17`

```json
{
  "fecha": "2026-10-08", "hora": 17,
  "vehiculos": [
    { "estadia_id": 42, "placa": "ABC123", "tipo_vehiculo": "Carro",
      "celda": "A-01", "ingreso_local": "07:12", "horas_dentro": 9.0,
      "estado": "Dentro del parqueadero" }
  ]
}
```

> **El detalle debe contar exactamente lo mismo que el gráfico.** Ambos usan el
> criterio temporal (entró antes de que terminara la hora y no había salido), no
> el estado de cobro: un vehículo pagado que sigue dentro ocupa el cupo igual.
> Si difieren, la gráfica deja de explicar nada.

`hora` fuera de 0–23: `400 validacion`.

---

## 4.6 Mensualidades

### `GET /api/customers/plans`

| Parámetro | Nota |
|---|---|
| `q` | Nombre, documento, teléfono o placa |
| `estado` | `ACTIVE\|EXPIRING\|EXPIRED\|CANCELLED\|NO_PLAN` |
| `solo_saldo` | `true` deja fuera a quien ya pagó |

```json
{
  "total": 6,
  "clientes": [
    {
      "cliente_id": 1, "nombre": "Ana Gómez",
      "documento": { "tipo": "CC", "numero": "10998877" }, "telefono": "3001112233",
      "suscripcion_id": 1, "plan": "Mensualidad Carro",
      "placas": ["ABC123", "XYZ789"],
      "inicio": "2026-09-30", "vence": "2026-10-30",
      "estado": "VIGENTE", "estado_texto": "VIGENTE · en 22 d",
      "dias_restantes": 22,
      "valor": "90000.00", "pagado": "0.00", "saldo": "90000.00"
    }
  ]
}
```

El estado se **deriva de la fecha**, no de la columna `status`. Un cliente sin
plan aparece con `estado: "NO_PLAN"`.

### `POST /api/customers`

```json
{
  "nombre": "Ana Gómez",
  "documento": { "tipo": "CC", "numero": "10998877" },
  "telefono": "3001112233", "correo": null, "direccion": null,
  "placas": ["ABC123", "XYZ789"]
}
```

Documento repetido: `409 conflicto`. Las placas nuevas se crean y se asocian en
la misma operación (`attach_vehicle`).

### `GET /api/customers/{id}` · `GET /api/customers/{id}/vehicles`

Ficha y placas del cliente.

### `POST /api/customers/{id}/vehicles`

```json
{ "placa": "new999", "tipo_vehiculo": "CAR" }
```

Placa de otro cliente: `409 conflicto`.

### `POST /api/subscriptions`

```json
{
  "cliente_id": 1,
  "plan": "Mensualidad Carro",
  "placas": ["ABC123"],
  "inicio": "2026-10-08",
  "meses": 1,
  "valor": "90000.00",
  "horario": { "desde": "06:00", "hasta": "20:00" }
}
```

Reglas: exige ≥ 1 placa; `horario` con ambas horas o ninguna; el vencimiento se
calcula con `_month_end` (fin de mes real, no 30 días).

### `POST /api/subscriptions/{id}/pay`

```json
{
  "metodo": "CASH", "monto": "90000.00",
  "efectivo_recibido": "100000.00", "referencia": null
}
```

Sólo `CASH` acepta efectivo recibido y cambio.

### `POST /api/subscriptions/{id}/renew` — **Renovar**

```json
{
  "metodo": "CASH",
  "monto": "95000.00",
  "efectivo_recibido": "100000.00",
  "meses": 1,
  "nombre_plan": null,
  "referencia": null
}
```

```json
{
  "suscripcion_anterior": 1,
  "suscripcion_nueva": 2,
  "pago_id": 501,
  "inicio": "2026-10-30",
  "vence": "2026-11-29"
}
```

**Una sola transacción**: crea el período y cobra. Si el cobro falla, no queda
plan creado sin pagar.

Regla de fechas:
- Plan **no vencido** → el nuevo período empieza **al día siguiente** del
  vencimiento (renovar antes no regala días).
- Plan **vencido** → empieza **hoy**, para no perder cobertura.

### `POST /api/subscriptions/{id}/cancel`

```json
{ "motivo": "Cliente se retiró" }
```

Conserva el historial de pagos.

### `GET /api/subscriptions/alerts?dias_aviso=7`

Planes por vencer o vencidos **con saldo**. `status`: `POR_VENCER`, `VENCIDA`.

### `POST /api/agreements`

```json
{ "cliente_id": 1, "nombre": "Convenio centro comercial",
  "tipo_descuento": "PERCENT", "valor": "15.00",
  "valido_desde": "2026-01-01", "valido_hasta": null }
```

---

## 4.7 Caja

### `POST /api/cash/shifts`

```json
{ "monto_inicial": "50000.00" }
```

Si ya hay un turno abierto del usuario: `409 conflicto`.

### `GET /api/cash/shifts?abiertos=true`

### `GET /api/cash/shifts/{id}/expected`

```json
{ "esperado": "235000.00", "apertura": "50000.00", "cobros_efectivo": 18 }
```

### `POST /api/cash/shifts/{id}/close`

```json
{ "monto_contado": "233500.00" }
```

```json
{ "esperado": "235000.00", "contado": "233500.00",
  "diferencia": "-1500.00", "estado": "CLOSED" }
```

---

## 4.8 Configuración

### `GET /api/tariffs` · `POST /api/tariffs`

```json
{ "tipo_vehiculo": "CAR", "nombre": "Hora carro",
  "esquema": "HOUR", "monto": "5000.00",
  "tramos": [{ "desde_minuto": 0, "hasta_minuto": 60, "monto": "5000.00",
               "gracia_minutos": 5 }] }
```

### `GET|POST /api/users`

```json
{ "usuario": "op1", "nombre_completo": "Operador Uno",
  "contraseña": "…", "rol": "OPERATOR" }
```

Sólo el super administrador puede crear otro super administrador.

### `PATCH /api/users/{id}` · `PATCH /api/users/{id}/password` · `DELETE /api/users/{id}`

Desactivar revoca las sesiones del usuario.

### `GET|PATCH /api/site` — Datos del parqueadero · **sólo super admin**

```json
{ "nombre": "Parqueadero Centro", "nit": "900.123.456-7",
  "direccion": "Calle 45 # 12-30", "telefono": "601 1234567",
  "capacidad_total": 30 }
```

### `GET|PATCH /api/receipt-template` — Plantilla · **sólo super admin**

```json
{ "nombre_plantilla": "Plantilla predeterminada", "nombre_parqueadero": "PARKIUM",
  "nit": "900.123.456-7", "direccion": "…", "encabezado": null,
  "terminos": "TÉRMINOS Y CONDICIONES\n…", "pie": "PARKIUM - Todos los derechos reservados.",
  "mostrar_codigo_barras": true, "mostrar_qr": true }
```

---

## 4.9 Reportes

### `GET /api/reports/summary?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` · **sólo super admin**

```json
{
  "rotacion": "1845000.00", "mensualidades": "675000.00", "total": "2520000.00",
  "por_metodo": [{ "etiqueta": "Efectivo", "valor": "1800000.00", "cantidad": 320 }],
  "por_tipo_vehiculo": [], "por_empleado": [], "por_tarifa": []
}
```

Por defecto, los últimos 30 días.

### `GET /api/dashboard` — Admin y operador

```json
{
  "ocupacion": { "capacidad_total": 30, "ocupados": 6, "disponibles": 24 },
  "hoy": { "ingresos": "210000.00", "salidas_cobradas": 12, "mensualidades": "…" },
  "generado_en": "2026-10-08T14:32:10+00:00"
}
```

### Exportaciones

| Ruta | Formato |
|---|---|
| `GET /api/reports/summary.csv` | CSV UTF-8 **con BOM** (Excel lo abre sin configuración) |
| `GET /api/reports/summary.json` | JSON; importes **como texto** |
| `GET /api/reports/summary.xlsx` | XLSX de una hoja |
| `GET /api/reports/summary.pdf` | PDF con tabla y estilo de marca |
| `GET /api/reports/full.xlsx` | XLSX completo: 5 hojas + 2 gráficos |

---

## 4.10 Seguridad del reloj

### `GET /api/clock/status`

```json
{
  "ok": true,
  "verificada": true,
  "fuente": "FUENTE_EXTERNA",
  "hora_sistema": "2026-10-08T14:32:10+00:00",
  "hora_referencia": "2026-10-08T14:32:11+00:00",
  "deriva_segundos": -1.0,
  "deriva_texto": "-1 s",
  "mensaje": "Hora verificada contra una fuente externa."
}
```

### `POST /api/clock/verify`

```json
{ "usar_red": true }
```

Compara contra la cabecera `Date` de un servidor externo y, si coincide,
**reancora** el reloj del servidor. Es la vía de recuperación cuando el operador
corrige la hora del equipo.

---

## 4.11 Salud y mantenimiento

### `GET /api/health`

```json
{ "estado": "ok", "version_esquema": 3, "motor": "postgresql",
  "sesiones_activas": 4, "ultimo_respaldo": "2026-10-08T02:00:00+00:00" }
```

---

## 4.12 Servicios externos

| Servicio | Uso | Estado |
|---|---|---|
| **Fuente de hora externa** | Verificación del reloj por cabecera HTTP `Date`. Por defecto `https://www.google.com/generate_204`, configurable con `PARKIUM_TIME_SOURCE_URL`. Se llama **en un hilo con espera máxima** de 6 s. | **Activo** |
| **Proveedor Tecnológico de facturación electrónica** | Contrato `InvoiceProvider`; `DisabledProvider` falla siempre. `PARKIUM_EINVOICE_PROVIDER=DISABLED`. | **Desactivado** |
| **Spooler de Windows** | ESC/POS vía `pywin32`. Sólo si el servidor es Windows. | **Depende del despliegue** |
| **Correo / SMS / push** | — | **No existen** en el original |

No hay pasarela de pago: los cuatro métodos son **registro manual** del
operador. La web no debe añadir una sin decisión del negocio.

---

## 4.13 Notas de implementación por endpoint

### `POST /api/checkout` — el más delicado

```
1. check_before_billing(usuario)        # 400 si el reloj no es confiable
2. BEGIN IMMEDIATE
3.   buscar la estadía ACTIVE por placa
4.   cotizar con la tarifa vigente
5.   validar método, monto y efectivo recibido
6.   validar turno de caja abierto si es CASH
7.   INSERT payments  (con idempotency_key)
8.   UPDATE parking_stays SET exit_at, status='PAID', calculated_amount
9.   issue_receipt()                    # número consecutivo dentro de la transacción
10.  INSERT audit_logs
11. COMMIT
```

Cualquier fallo entre 2 y 11 revierte todo. **Nunca** se emite un comprobante sin
cobro, ni se registra un cobro sin cerrar la estadía.

### `POST /api/subscriptions/{id}/renew` — segundo más delicado

Igual estructura. Además calcula el período con `_month_end` **antes** de abrir
la transacción, porque resolver la fecha del sitio abre otra conexión y, si se
hace con una escritura en curso, esa conexión espera el bloqueo: la operación se
quedaba **más de medio minuto colgada**.

### `GET /api/receipts/{id}/pdf` y `/image`

Se generan en el servidor con `reportlab` y Pillow, igual que el original. En
la web el cliente no necesita esas librerías; sólo descargar el resultado.

### `GET /r/{token}`

Ruta **fuera de `/api`** y **sin autenticación**. Renderiza una vista mínima y
sin navegación, pensada para que se escanee desde el papel. Debe incluir
`Cache-Control: no-store` y no revelar datos del cliente más allá del comprobante.