# 05 — Instrucciones por módulo

Orden de implementación recomendado. Cada módulo indica objetivo, pantallas,
lógica, endpoints, tablas, **criterios de aceptación verificables** y
**pruebas requeridas**.

Los módulos 1 a 9 son los que dan paridad funcional. El 10 es opcional.

---

## 1. Fundaciones e infraestructura

### Objetivo y alcance

Levantar el esqueleto: base de datos con Alembic, API FastAPI con
autenticación, y el esqueleto del frontend con tema y rutas. Nada de negocio.

### Tareas

1. **Base de datos**
   - Crear `backend/` con `pyproject.toml`, `alembic.ini` y `migrations/`.
   - Revisión `0001_initial`: el esquema de `sql/001_initial_schema.sql`
     traducido a PostgreSQL (§3.9.1 de `03-esquema-base-datos.md`).
   - Revisión `0002_timestamps`: `TEXT` → `TIMESTAMPTZ` (§3.9.3).
   - Revisión `0003_constraints`: las 4 restricciones de §3.9.4.
   - Cargar `SEED_DATA` traducido a `ON CONFLICT DO NOTHING`.

2. **Conector de dominio**
   - `backend/app/db.py`: engine, sesión y dependencia `get_db`.
   - `backend/app/domain/__init__.py`.
   - Sustituir `row_factory = sqlite3.Row` por una capa de acceso uniforme.

3. **API**
   - `backend/app/main.py`: FastAPI, CORS restringido, estáticos, `/api/health`.
   - `backend/app/config.py` con `pydantic-settings` (ver §8 de este documento).
   - Middleware de gestión de errores que traduce cada excepción de dominio al
     código de §4.1.

4. **Frontend**
   - Vite + React + TypeScript, `ThemeProvider`, `Shell`, rutas y páginas
     vacías.
   - `api/client.ts` con cliente HTTP tipado, manejo de `401` y de `403`.

### Lógica y validaciones

- Toda la validación de esquema con Pydantic; las reglas de negocio **nunca** en
  el frontend.
- El frontend oculta botones por rol, pero **la API es la que autoriza**.

### Criterios de aceptación

- [ ] `alembic upgrade head` crea las 25 tablas en una base vacía.
- [ ] `alembic downgrade base` las elimina sin error.
- [ ] `SELECT count(*) FROM roles` = 3, `vehicle_types` = 3, `payment_methods` = 4.
- [ ] `GET /api/health` responde 200 con `version_esquema: 3`.
- [ ] El tema claro y el oscuro se alternan y se recuerda al recargar.
- [ ] Un usuario sin sesión que pide cualquier ruta protegida es enviado a `/login`.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | La migración crea el esquema completo; `SEED_DATA` es idempotente (se puede correr dos veces). |
| Integración | `GET /api/health`. |
| e2e | Login con sesión vacía, tema alternando, ruta protegida redirige. |

---

## 2. Autenticación y sesiones

### Objetivo y alcance

Replicar exactamente `app/services/authentication.py`: mismo scrypt, misma
jerarquía de roles, misma duración.

### Tareas

1. Copiar `app/services/authentication.py` a `backend/app/domain/` adaptando
   únicamente el acceso a la base.
2. `backend/app/deps.py`:
   - `get_current_user` — lee la cookie, valida contra `user_sessions`.
   - `require_role(*roles)` — port literal de `require_role`.
   - `require_admin`, `require_superadmin`.
3. `backend/app/api/auth.py` con los endpoints de §4.2.
4. `frontend/src/pages/LoginPage.tsx` con el fondo y la tarjeta de cristal.
5. `frontend/src/pages/RecoveryPage.tsx`.
6. `frontend/src/api/auth.ts` y contexto `AuthContext`.

### Lógica y validaciones

Verificar textualmente, sin cambiar el comportamiento:

| Regla | Valor | Fuente |
|---|---|---|
| Algoritmo | scrypt N=16384, r=8, p=1 | `SCRYPT_N/R/P` |
| Longitud de contraseña | 10 a 256 | `PASSWORD_MIN_LENGTH/MAX` |
| Formato de usuario | `^[A-Za-z0-9._-]{3,60}$` | `_USERNAME_PATTERN` |
| Duración de sesión | 12 h | `SESSION_DURATION` |
| Almacenamiento | SHA-256 del token, nunca el token | `_token_hash` |
| Jerarquía | `SUPERADMIN` satisface cualquier `require_role` | `_ROLE_IMPLICITS` |
| Recovery | Sólo **administrador**, por consola local | `reset_administrator_password` |

> **Crítico:** `require_role` no da permisos heredados parciales. `ADMIN` sólo
> pasa las llamadas que aceptan `ADMIN`; no pasa las que exigen
> `SUPERADMIN`. Si la web implementa «admin ≥ operador» por comodidad, cambia el
> modelo de autorización.

### Criterios de aceptación

- [ ] `hash_password` produce el mismo formato que el original y `verify_password`
      acepta los hashes ya existentes.
- [ ] Un token expirado da `401`; uno revocado también.
- [ ] La cookie es `HttpOnly`, `Secure` y `SameSite=Lax`; **nunca** se guarda el
      token en `localStorage`.
- [ ] El frontend no puede ver la cookie desde JavaScript.
- [ ] Un `ADMIN` recibe `403` en `/api/site`.
- [ ] `POST /api/auth/first-user` responde `409` si ya existe un usuario.
- [ ] Cambiar la contraseña de un usuario **revoca** sus sesiones activas.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | Hash/verificación; matriz completa rol × endpoint; formato de usuario; longitud de contraseña. |
| Integración | Login, logout, sesión expirada, cambio de contraseña. |
| e2e | Inicio de sesión completo; intento de acceso directo a `/reportes` como admin → bloqueado. |

---

## 3. Operación: entrada, cotización y cobro

### Objetivo y alcance

El módulo más crítico: maneja dinero. Portar `parking_operations.py` con
fidelidad absoluta.

### Tareas

1. Copiar `app/services/parking_operations.py` y sustituir `julianday()` por
   comparación directa de `TIMESTAMPTZ`.
2. Implementar §4.3: `POST /api/stays`, `GET /api/stays/{placa}/quote`,
   `POST /api/checkout`, `POST /api/payments/{id}/void`, `GET /api/occupancy`.
3. `frontend/src/pages/OperationsPage.tsx` con el flujo de tres pasos: ingreso,
   cotización, cobro.
4. Campo de **efectivo recibido con cambio en vivo**, replicando
   `main_window._update_change`.
5. Selector de forma de pago que muestra y oculta el bloque de efectivo, como
   `_toggle_cash_fields`.

### Lógica y validaciones

| Regla | Detalle | Fuente |
|---|---|---|
| Normalización de placa | Mayúsculas sin espacios; 3–15 alfanuméricos | `_normalise_plate` |
| Hora de confianza | `check_before_billing` antes de cotizar **y** de cobrar | `_require_reliable_clock` |
| Estatus activos | `ACTIVE`, `PENDING_PAYMENT`, `PAID`, `CANCELLED` | `_ACTIVE_STATUSES` |
| Idempotencia | `Idempotency-Key` única en `payments` | `collect_payment` |
| Efectivo recibido | Sólo `CASH` | `_cash_movement` equivalente |
| Turno de caja | Obligatorio en `CASH` | `cash_shifts` |
| Transacción | `BEGIN IMMEDIATE` → cobro + cierre + recibo juntos | `collect_payment` |
| Tiempo transcurrido | Reloj monotónico si entrada y salida comparten proceso | `elapsed_minutes` |
| Vacío | Una mensualidad vigente puede dar total 0 | `docs/manual-usuario.md` |

### Esquemas de cobro

Los 7 de `BILLING_SCHEMES` deben comportarse idéntico a `calculate_tariff`:

| Esquema | Regla |
|---|---|
| `MINUTE` | minutos × monto unitario |
| `HOUR` | horas redondeadas hacia arriba × monto |
| `HOUR_FRACTION` | fracción de hora (30 min por defecto) |
| `FLAT_ENTRY` | valor fijo al ingresar |
| `BLOCKS` | bloques de N minutos |
| `DAY` | valor por día |
| `NIGHT` | tarifa nocturna |

Cada uno tiene `grace_minutes` y `fraction_minutes`. **Portar la función, no
reescribirla**, y verificarla con los mismos casos que las pruebas existentes.

### Criterios de aceptación

- [ ] Registrar una placa por primera vez crea el vehículo y la factura de ingreso.
- [ ] Registrar dos veces la misma placa con estadía activa da `409`.
- [ ] Un plan vigente da cotización 0 dentro de su horario y la tarifa normal
      fuera de él.
- [ ] Cotizar **no** cierra la estadía.
- [ ] Cobrar cierra la estadía, registra el pago y emite el recibo **juntos**.
- [ ] Efectivo insuficiente: `400` con el mensaje `Faltan $X`.
- [ ] `CARD`, `TRANSFER` y `DIGITAL_WALLET` rechazan `efectivo_recibido`.
- [ ] Cobrar en efectivo sin turno abierto se rechaza.
- [ ] Repetir la misma `Idempotency-Key` devuelve el mismo pago y **no** cobra dos
      veces.
- [ ] Con el reloj desviado, cotizar y cobrar devuelven `400 reloj_no_confiable`.
- [ ] Los 7 esquemas de cobro producen los mismos importes que el original para
      las mismas entradas.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | Los 7 esquemas con tabla de casos límite (0 min, fracción exacta, gracia, cruce de medianoche). |
| Unitarias | Normalización de placa; validación de horario permitido que cruza medianoche. |
| Integración | Entrada → cotización → cobro → comprobante, con verificación de la base. |
| Integración | Rollback: si falla el recibo, no debe quedar el cobro. |
| e2e | El flujo completo del operador con el cálculo de cambio en pantalla. |

---

## 4. Comprobantes e impresión

### Objetivo y alcance

Emitir, previsualizar, reimprimir e imprimir exactamente los mismos documentos.

### Tareas

1. Copiar `app/services/receipts.py` **sin cambios funcionales**.
2. Endpoints de §4.4.
3. Vista previa en el navegador antes de imprimir.
4. Ruta pública `GET /r/{token}` fuera de la SPA.
5. Impresión del navegador con CSS `@page` para el ancho del rollo.
6. `frontend/src/components/ReceiptPreview.tsx`.

### Lógica y validaciones

| Regla | Detalle |
|---|---|
| Numeración | Consecutiva **por sede**, reservada dentro de la transacción |
| Tipos | `ENTRY`, `EXIT`, `SUBSCRIPTION`, `ADJUSTMENT` |
| Regla | Un `EXIT` exige `stay_id` |
| Código de barras | Code128 con la **placa** en mayúsculas; respaldo: número de documento |
| QR | URL pública del comprobante |
| Plantilla | Términos y pie desde `receipt_templates` |
| Reimpresión | Incrementa `reprint_count` y escribe auditoría |
| Anchos | PNG térmico 58 u 80 mm |

### Criterios de aceptación

- [ ] Los comprobantes de dos sedes distintas empiezan su numeración aparte.
- [ ] La vista previa muestra exactamente lo que se va a imprimir.
- [ ] Reimprimir incrementa el contador y deja registro en auditoría.
- [ ] El QR apunta a una URL pública que resuelve el comprobante **sólo** con su
      token.
- [ ] El código de barras contiene la placa en mayúsculas.
- [ ] Los términos y el pie salen de la plantilla activa.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | `receipt_lines`, `barcode_value`, plantilla y sus valores por defecto. |
| Integración | Emitir, consultar, reimprimir; numeración concurrente sin duplicados. |
| e2e | Reimpresión desde el histórico de factura y de recibo. |

---

## 5. Histórico

### Objetivo y alcance

Búsqueda con los mismos filtros y la ocupación por hora.

### Tareas

1. Copiar `app/services/history.py` y sustituir `julianday()`.
2. `GET /api/history` con los 5 filtros.
3. `GET /api/occupancy/hourly` y `GET /api/occupancy/detail`.
4. `frontend/src/components/DatePicker/` — replicar `calendar_popup.py`:
   navegación de meses, días atenuados, botón «Hoy», y **el campo sigue
   aceptando escritura a mano**.
5. `frontend/src/components/charts/OccupancyChart.tsx`.

### Lógica y validaciones

| Regla | Detalle |
|---|---|
| Sin rango | Se limita al día de hoy |
| `desde > hasta` | `400 validacion` |
| Horas | Siempre `hh:mm` en 24 h |
| Sin salida | La hora queda `—` y el estado dice «Dentro del parqueadero» |
| Franjas | **Hora local del sitio**, no UTC |
| Serie | Siempre 24 puntos, aunque el día esté vacío |
| Criterio | Temporal en gráfico **y** detalle, idéntico |
| Sin salida | `salida = ahora`, nunca «hasta el infinito» |

### Escalado del gráfico

`_escala()` redondea a 1-2-3-5 por potencia de diez, y la rejilla elige un
número de líneas que divida el tope. Sin esto, con 30 cupos y 4 vehículos la
curva se aplasta y no se ve la forma.

### Criterios de aceptación

- [ ] Los 4 filtros funcionan solos y combinados.
- [ ] Sin rango devuelve sólo el día de hoy.
- [ ] La serie devuelve 24 puntos; un día futuro devuelve 0 en todos.
- [ ] `detail` lista **exactamente** tantas placas como marca el gráfico en esa
      hora.
- [ ] Un vehículo pagado que sigue dentro **aparece** en el detalle.
- [ ] El calendario acepta `2026-10-06`, `06/10/2026`, `06.10.2026` y `6-10-26`.
- [ ] Los nombres de día y mes salen **en español**, sin depender del idioma del
      navegador.
- [ ] Las etiquetas del eje son cifras redondas y regulares.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | `_hora_local_utc` con zona `America/Bogota`; serie de 24 puntos; límite de búsqueda. |
| Unitarias | `_escala` para máximo de 1 a 60 y 300. |
| Unitarias | Lectura de fechas en los 4 formatos; nombres en español. |
| Integración | Gráfico y detalle coinciden placa a placa. |
| e2e | Filtrar, elegir fecha en el calendario, reimprimir. |

---

## 6. Mensualidades

### Objetivo y alcance

Alta de clientes, planes, saldos, **renovación** y cobro. Replicar
`app/ui/subscription_view.py` completo.

### Tareas

1. Copiar `app/services/subscriptions.py`.
2. Endpoints de §4.6.
3. `frontend/src/pages/SubscriptionsPage.tsx` con:
   - Listado de clientes (7 columnas) + ficha de detalle.
   - Filtros: búsqueda, estado, «sólo con saldo».
   - Cinco botones con habilitación según la fila.
4. Diálogos de alta de cliente, alta de plan, cobro/renovación y cancelación.

### Lógica y validaciones

| Regla | Detalle | Fuente |
|---|---|---|
| Documento único | `409` si se repite | `create_customer` |
| Estados | Derivados de `expires_on`, no de la columna | `_effective_status` |
| Placas | Alta exige ≥ 1 | `create_subscription` |
| Horario | Ambas horas o ninguna | `_time_value` |
| Renovación | Una sola transacción: período + cobro | `renew_subscription` |
| Encadenado | No vencido → al día siguiente; vencido → hoy | `renew_subscription` |
| Fin de mes | `_month_end`, real, con bisiesto | `_month_end` |
| Cambio | Sólo `CASH` | `_cash_movement` |
| Cancelar | Conserva el historial de pagos | `cancel_subscription` |
| Saldo | Nunca negativo | `PortfolioItem` |

### Detalle de rendimiento

La fecha del sitio se resuelve **antes** de abrir la transacción de escritura.
`today_for_site` abre su propia conexión; si se le llama con la escritura en
curso, esa conexión espera el bloqueo y la renovación se queda **más de medio
minuto colgada**. Verificado: 33 s → 0,03 s.

### Criterios de aceptación

- [ ] Un cliente sin mensualidad **aparece** en el listado con estado `SIN PLAN`.
- [ ] Un plan vencido se muestra `VENCIDA` aunque la columna diga `ACTIVE`.
- [ ] La búsqueda funciona por nombre, documento, teléfono y **placa**.
- [ ] El filtro de estado acepta el código interno y la etiqueta en español.
- [ ] Renovar un plan vigente encadena al día siguiente.
- [ ] Renovar un plan vencido arranca hoy y el anterior queda `EXPIRED`.
- [ ] 31 de enero + 1 mes = 28 de febrero (29 si es bisiesto).
- [ ] La renovación en efectivo guarda `efectivo_recibido` y `cambio`.
- [ ] Efectivo insuficiente indica cuánto falta.
- [ ] Cancelar conserva los pagos.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | Los 18 casos de `SubscriptionPortfolioTests` del original, adaptados. |
| Unitarias | `_month_end` con bisiesto y fin de mes. |
| Integración | Renovar en las 4 formas de pago; rechazo por turno cerrado. |
| e2e | Alta de cliente con placas, alta de plan, cobro, renovación, cancelación. |

---

## 7. Seguridad del reloj · **el módulo de mayor riesgo**

### Objetivo y alcance

Replicar `app/services/time_integrity.py`. **Este es el punto donde la web
difiere de verdad del original**, porque el reloj monotónico de Python no
existe en el navegador.

### Por qué importa

La función existe para impedir que alguien altere la hora del equipo y cobre
con una fecha manipulada. En el escritorio hay dos referencias: el reloj
monotónico del proceso y la hora del sistema. En la web hay una sola: **la hora
del servidor**, que el cliente no controla.

### El problema concreto

`verify_clock` guarda un ancla en `clock_anchors` (una fila) con `boot_utc` y
`boot_monotonic`, y calcula la deriva entre la hora del sistema y la proyección
del ancla. Si alguien adelanta el reloj del equipo, la deriva se dispara, el
cobro se bloquea, y una verificación externa correcta **reancora** el reloj.

En la web el diseño cambia de naturaleza:

| Aspecto | Escritorio | Web |
|---|---|---|
| Reloj manipulable | El del equipo | **Ninguno**: el cliente no controla la hora |
| Ancla | Por proceso (`boot_id`) | Por **servidor**, con un identificador de despliegue |
| Fuente externa | Cabecera `Date` | **La propia hora del servidor** |
| Deriva | Sistema vs monotónico | **Servidor vs reloj de la máquina** |

### Diseño propuesto

1. **El servidor es la autoridad.** La API devuelve la hora y **la web no valida
   nada en el cliente**.
2. **Ancla persistente** en `clock_anchors` (la tabla ya existe):
   - `boot_id` → identificador del proceso del servidor (`current_boot_id`).
   - `boot_utc` → hora del servidor al arrancar.
   - `boot_monotonic` → `time.monotonic()` del proceso del servidor.
   - `last_trusted_utc` → **sólo avanza si la verificación es limpia**.
   - `max_drift_seconds` → evidencia acumulada, no veredicto de bloqueo.
3. **`check_before_billing` se ejecuta en cada cotización y cobro**, en el
   servidor, y es bloqueante.
4. **Verificación contra fuente externa** disponible como botón, con la cabecera
   `Date` y **en hilo con espera máxima**, porque la resolución de nombres no
   respeta el timeout de `urlopen` y congelaba la ventana.
5. **Reanclaje**: una verificación externa correcta reancora `boot_utc` y
   `boot_monotonic` desde ese momento. Sin esto, corregir la hora del equipo no
   basta y el sistema queda bloqueado hasta reiniciar.

### Si el servidor corre en una plataforma sin reloj monotónico

Es el caso de algunos contenedores. Alternativa: usar el reloj del servidor
como única referencia y conservar `clock_checks` como evidencia, aceptando que
la detección de manipulación pierde precisión. **Debe ser una decisión
explícita**, no un silencio.

### Criterios de aceptación

- [ ] Cada cotización y cada cobro ejecutan la verificación del reloj.
- [ ] Con el reloj del servidor desviado, ambos devuelven `400 reloj_no_confiable`.
- [ ] `last_trusted_utc` **no** avanza mientras la verificación no sea limpia.
- [ ] Una verificación externa correcta reancla el reloj y reactiva el cobro.
- [ ] Si la red no responde, la verificación local sigue siendo válida y el
      cobro **no** se detiene.
- [ ] Cada verificación queda en `clock_checks` con fuente y deriva.
- [ ] El frontend **no** calcula ni valida hora alguna.

### Pruebas

| Tipo | Contenido |
|---|---|
| Unitarias | Anclaje nuevo; deriva dentro y fuera de tolerancia; recuperación; reananclaje. |
| Integración | Cobro con reloj desviado → bloqueado; tras verificar → permitido. |
| Integración | Fuente externa inaccesible → el cobro **sigue** funcionando. |
| e2e | El botón «Verificar hora» de la barra del dashboard. |

---

## 8. Configuración y administración

### Objetivo y alcance

Las 6 pestañas de `_show_admin`, con las restricciones de rol ya definidas.

### Tareas

1. Copiar `app/services/site_settings.py` y `app/services/authentication.py`
   (parte de usuarios).
2. Endpoints de §4.8.
3. `frontend/src/pages/SettingsPage.tsx` con pestañas condicionadas por rol:
   - **Tarifas** — todos los administradores
   - **Usuarios** — todos los administradores
   - **Caja** — todos los administradores
   - **Seguridad** — todos los administradores
   - **Parqueadero** — sólo super administrador
   - **Plantilla de factura** — sólo super administrador

### Lógica y validaciones

| Regla | Detalle |
|---|---|
| Tarifas | Versionadas; una anterior no se edita, se crea otra con vigencia |
| Usuarios | Sólo el super admin crea otro super admin |
| Contraseña ajena | Un admin cambia la de un normal; **nunca** la del super admin |
| Desactivar | Revoca las sesiones del usuario |
| Datos fiscales | Sólo super admin (`require_superadmin`) |
| Plantilla | Sólo super admin; incluye términos y pie |

### Criterios de aceptación

- [ ] Un `OPERATOR` no ve Configuración; si fuerza la URL, recibe `403`.
- [ ] Un `ADMIN` no ve las pestañas Parqueadero ni Plantilla, y su API responde `403`.
- [ ] Crear un super admin exige rol super admin.
- [ ] Un admin no puede restablecer la contraseña del super admin.
- [ ] Desactivar un usuario invalida sus sesiones activas.
- [ ] Crear una tarifa nueva no altera el cobro de una estadía que ya usa la anterior.

### Pruebas

| Tipo | Contenido |
|---|---|
| Integración | Matriz completa rol × pestaña × endpoint. |
| Unitarias | Validación de plantillas y de la política de contraseñas. |
| e2e | Crear tarifa → usarla en una cotización. |

---

## 9. Dashboard y reportes

### Objetivo y alcance

Tarjetas, gráfico de ocupación y exportaciones.

### Tareas

1. Copiar `app/services/reports.py` y `app/services/exporters.py`.
2. `GET /api/dashboard`, `GET /api/reports/summary` y las 5 exportaciones.
3. `frontend/src/pages/DashboardPage.tsx` con tarjetas, reloj y gráfico.
4. `frontend/src/pages/ReportsPage.tsx` (sólo super admin).

### Lógica y validaciones

| Regla | Detalle |
|---|---|
| Dashboard | Admin **y** operador |
| Consolidado | **Sólo** super admin (`_require_report_access`) |
| Exportación completa | Sólo super admin |
| CSV | UTF-8 **con BOM** para que Excel reconozca los acentos |
| JSON | Importes **como texto**, sin pérdida de precisión |
| XLSX completo | 5 hojas y 2 gráficos |

### Criterios de aceptación

- [ ] Un operador ve el dashboard del día pero no el consolidado.
- [ ] Un admin ve el dashboard pero recibe `403` en `/api/reports/summary`.
- [ ] El CSV abre en Excel con los acentos correctos.
- [ ] El JSON devuelve los importes como cadena.
- [ ] El XLSX completo trae las 5 hojas y los 2 gráficos.

### Pruebas

| Tipo | Contenido |
|---|---|
| Integración | Matriz de permisos de reportes y exportaciones. |
| Unitarias | Agregados del consolidado; totales que cuadran con `payments`. |
| e2e | Descargar las 5 exportaciones y abrirlas. |

---

## 10. Facturación electrónica · **no implementar**

### Objetivo y alcance

**No es parte de la versión web.** Se documenta para evitar que alguien lo active
por error.

### Reglas

- `PARKIUM_EINVOICE_PROVIDER=DISABLED` y `DisabledProvider` **falla siempre**
  con un mensaje que explica cómo habilitarlo.
- La tabla `electronic_invoices` puede existir, pero queda vacía.
- La factura de ingreso y el recibo de salida son **documentos internos**. No
  son facturación electrónica y no deben presentarse como tales.
- Habilitarlo exige un **Proveedor Tecnológico autorizado** y es una decisión de
  negocio y de cumplimiento legal, no técnica. Ver
  [12-preguntas-abiertas.md](12-preguntas-abiertas.md) §4.

### Criterio

- [ ] Ninguna pantalla presenta la factura interna como documento electrónico.
- [ ] `issue_receipt_invoice` falla con un mensaje explicativo, nunca simula una
      autorización.

---

## 11. Atributos transversales

### Rendimiento

| Requisito | Medida |
|---|---|
| Primera carga del login | < 2 s en red de oficina |
| Listado del histórico | < 800 ms con 500 filas |
| Cotización de salida | < 300 ms |
| **Cobro de salida** | < 1 s |
| Exportación XLSX completa | < 10 s |

### Seguridad

- [ ] HTTPS obligatorio en producción; `Secure` en la cookie de sesión.
- [ ] `PARKIUM_EINVOICE_PROVIDER` y la clave de la base **nunca** en el
      repositorio.
- [ ] CORS limitado a los orígenes del frontend.
- [ ] Límite de peticiones en login y en cotizaciones.
- [ ] Validación de toda entrada con Pydantic.
- [ ] Errores al cliente sin rastro de pila ni detalles internos.
- [ ] `audit_logs.ip_address` **se llena** en la web (hoy está disponible pero
      sin usar).
- [ ] Impresión de comprobante requiere rol.

### Observabilidad

- [ ] Registro estructurado con petición, latencia y usuario.
- [ ] Correlación por identificador de petición de principio a fin.
- [ ] Alerta si `verify_clock` marca el reloj como sospechoso.
- [ ] Métricas: cobros por minuto, tasa de error por endpoint, latencia de la
      cotización.
- [ ] `GET /api/health` para el sonda de disponibilidad.