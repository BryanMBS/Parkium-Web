# Parkium — Versión web

Sistema de administración de parqueaderos (entrada, operación/cobro, caja, comprobantes,
mensualidades, histórico, dashboard, reportes y configuración) construido sobre las
especificaciones de `docs/` (14 archivos `.md`) y los recursos de `assets/`.

**Stack decidido:** FastAPI + `sqlite3` crudo (equivalente al original, listo para Postgres)
+ frontend React + TypeScript + Vite. La lógica de negocio **no se reescribe**: se reutiliza
desde `backend/app/domain/` (copia adaptada de `app/services/` del original).

> Stack adoptado por pregunta al usuario: **SQLite ya, listo para Postgres** y **MVP completo**
> (autenticación, operación/cobro, caja, comprobantes, mensualidades, histórico,
> dashboard, reportes y configuración).

---

## Estructura

```
Parkium Web/
├── docs/                    # 14 especificaciones .md (fuente de verdad)
├── assets/                  # logos y recursos de marca
│   ├── generated/logo.png, login_bg.jpg, icon_app.png
│   └── IMG/ (originales)
├── backend/                 # API FastAPI + lógica de negocio (sqlite3 crudo)
│   ├── app/main.py          # FastAPI, CORS, middleware de errores
│   ├── app/domain/*         # autenticación, cobros, caja, recibos, suscripciones, exporters (XLSX/PDF), …
│   ├── app/data/schema.sql  # 25 tablas
│   ├── app/data/seed.sql    # semillas idempotentes + tarifas
│   ├── scripts/             # create_first_admin.py, reset-admin.py, smoke_test.ps1,
│   │                        # migrate_multi_tenant.py, create_platform_admin.py, smoke_multi_tenant.py
│   └── requirements.txt
└── frontend/                # SPA React + TS + Vite
    ├── vite.config.ts       # proxy /api -> backend (mismo origen, cookie)
    ├── src/api/*            # cliente HTTP tipado (contratos de docs/04)
    ├── src/theme/           # paleta (docs/06), modo claro/oscuro, catálogos
    ├── src/components/      # Sidebar 235px, DatePicker, gráfico de ocupación, Modal
    └── src/pages/           # Login, Dashboard, Operación, Histórico, Mensualidades, …
```

---

## 1. Requisitos previos

| Capa | Requisito | Comprobado |
|------|-----------|------------|
| Backend | Python 3.10+ | Python 3.14 |
| Backend deps | `pip install -r backend/requirements.txt` | OK |
| Frontend | Node.js 18+ | Node 24.21.0 |
| Frontend deps | `npm install` en `frontend/` | OK |

---

## 2. Variables de entorno (backend)

Se leen desde `backend/app/config.py`. Las principales:

| Variable | Valor por defecto | Notas |
|----------|-------------------|-------|
| `PARKIUM_ENTORNO` | `desarrollo` | `produccion` activa cookie `secure` |
| `PARKIUM_SQLITE_PATH` | `<raiz>/runtime/parkium.db` | base de datos (no versionada: `runtime/` está en `.gitignore`) |
| `PARKIUM_DATA_DIR` | `<raiz>/runtime` | carpeta de datos |
| `PARKIUM_DURACION_SESION_HORAS` | `12` | vida de la sesión de cookie |
| `PARKIUM_ORIGENES_PERMITIDOS` | `http://localhost:5173,http://localhost:4173` | CORS del frontend |
| `PARKIUM_URL_PUBLICA_BASE` | `""` | base de los QR de los comprobantes |
| `PARKIUM_PROVEEDOR_FACTURACION` | `DISABLED` | facturación electrónica DESACTIVADA (docs/12 §4) |
| `PARKIUM_ADMIN_PLATAFORMA_CONTRASENA` | *(ninguna)* | sólo la lee `scripts/create_platform_admin.py`; no es runtime |

El frontend lee `PARKIUM_API_PORT` (por defecto `8000`) para su proxy Vite.

---

## 3. Primer superadministrador

El primer usuario se crea con `backend/scripts/create_first_admin.py`:

- **usuario:** `admin`
- **contraseña:** `Cambiame.123`
- **rol:** `SUPERADMIN` (id 1)

> La ruta `POST /api/auth/first-user` queda cerrada en cuanto existe un usuario
> (docs/04 §4.2, decisión docs/12 §2 opción A: recuperación de admin **no** expuesta por HTTP).

---

## 3-bis. Administrador de PLATAFORMA (multi-tenant)

El sistema es multi-tenant: cada cliente (tenant) tiene su propio espacio de
datos y el administrador de PLATAFORMA (`PLATFORM_ADMIN`, `tenant_id NULL`)
gestiona los clientes desde `/plataforma`, un espacio separado del operativo.

1. **Migrar el esquema** (idempotente; crea la tabla `tenants`, agrega
   `tenant_id` a las tablas de negocio, agrega `users.must_change_password`,
   reconstruye `vehicles` con `UNIQUE(tenant_id, plate)` y siembra el tenant
   demo «Parkaderos Demo S.A.S.»). Hace copia previa en `runtime/`:

   ```bash
   cd backend && python scripts/migrate_multi_tenant.py
   ```

2. **Crear el administrador de plataforma** (nunca lleva contraseña fija):

   ```bash
   cd backend
   # PowerShell: la contraseña NUNCA va en el código ni en el repositorio
   $env:PARKIUM_ADMIN_PLATAFORMA_CONTRASENA='<tu-contraseña>'
   python scripts/create_platform_admin.py
   # también acepta usuario en formato patrón (p. ej. plata.admin) sin env var,
   # pidiendo la contraseña por getpass
   ```

3. Ese usuario entra a **`/plataforma`** (Resumen, Clientes, Auditoría) y
   queda fuera de todas las rutas operativas; los usuarios de tenant reciben
   `403` en `/api/platform/*` (docs/04 §4.1). Crear un cliente es UNA
   transacción: tenant + primera sede (con tarifas y plantilla) + primer
   administrador con contraseña temporal obligada a cambio en el primer login.

**Cuotas:** al exceder `max_sites` o `max_users` la API responde `409` con
codigo `limite_plan_alcanzado` en el contrato `{ codigo, mensaje, detalle }`.

**Suspensión:** `POST /api/platform/tenants/{id}/suspend` bloquea el login
(mensaje exacto «Cuenta suspendida, contacta a soporte»), revoca las sesiones
activas del tenant dentro de la misma transacción y lo vuelve a comprobar en
`validate_session` (doble defensa). Los recibos públicos ya emitidos
(`/r/{token}`) **siguen visibles** mientras el cliente esté suspendido:
decisión documentada, el documento pertenece al pagador.

---

## 4. Levantar y probar

### Backend (desde `backend/`)

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> Ejecutar **sin** `--reload` para controlar el proceso manualmente. Con
> `PARKIUM_ENTORNO=produccion` la cookie de sesión usa `secure`.

### Frontend (desde `frontend/`)

```bash
npm run dev      # http://localhost:5173 (proxy /api -> backend)
npm run build    # producción
```

El proxy de Vite hace que la cookie de sesión viva en el mismo origen; no hay que
negociar CORS desde el navegador.

### Prueba de humo del backend

```powershell
powershell -ExecutionPolicy Bypass -File backend/scripts/smoke_test.ps1
```

Verifica: `health` → login `admin`/`Cambiame.123` → entrada con placa normalizada +
factura de ingreso → duplicado `409` → cotización → apertura de turno de caja →
cobro con `Idempotency-Key` → idempotencia (no duplica) → dashboard → importe insuficiente `400`.

> Usa una copia de la base (ver más abajo) o una base de desarrollo: la prueba **escribe**
> estadías, pagos y comprobantes.

### Prueba de humo multi-tenant (Fase 1-2 del módulo de plataforma)

Levanta un servidor de pruebas contra una **copia** de la base y ejecuta:

```powershell
cd backend
Copy-Item ..\runtime\parkium.db ..\runtime\_test_multi.db
$env:PARKIUM_SQLITE_PATH = (Resolve-Path ..\runtime\_test_multi.db).Path
python -m uvicorn app.main:app --port 8010
# en otra consola:
$env:PARKIUM_BASE_URL = 'http://127.0.0.1:8010'
$env:PARKIUM_ADMIN_PLATAFORMA_CONTRASENA = '<tu-contraseña-del-admin-de-plataforma>'
python scripts\smoke_multi_tenant.py
```

Cubre 29 comprobaciones: creación de tenants (transacción única), NIT inválido
`400`, cuotas `409 limite_plan_alcanzado` (sedes y usuarios), aislamiento de
placas y recibos entre tenants, suspensión con revocación de sesiones y mensaje
exacto de bloqueo, recibos públicos activos durante la suspensión,
reactivación, y auditoría con filtros.

---

## 5. Endpoints públicos

| Ruta | Autenticación | Descripción |
|------|---------------|-------------|
| `GET /api/health` | no | Estado del esquema y motor |
| `POST /api/auth/login` | no | Inicia sesión (cookie `parkium_sesion` HttpOnly) |
| `POST /api/auth/logout` | sí | Revoca la sesión |
| `GET /r/{token}` | **no** | Comprobante público por token del QR (docs/04 §4.13) |

> **Monitores externos:** la ruta del chequeo de salud es **`/api/health`**. El servidor
> **no** expone `/health` (sin prefijo `/api`); apuntar ahí produce 404 en cada sonda.

Todas las demás rutas de `/api` exigen sesión válida y el rol correspondiente.
El módulo de plataforma vive bajo **`/api/platform/*`** y exige rol
`PLATFORM_ADMIN` (espacio separado del operativo).

---

## 6. Contratos de la API

Los importes viajan **como cadena decimal** (nunca número JSON) y se formatean en el
frontend con `Intl.NumberFormat('es-CO')` → `$45.000,00` (docs/06 §6.12). Los errores
siguen el contrato `{ codigo, mensaje, detalle }` de docs/04 §4.1. Los cobros son
transaccionales (`BEGIN IMMEDIATE`) y soportan idempotencia por cabecera `Idempotency-Key`.

---

## 7. Aceptación de paridad funcional (docs/11)

Antes de considerar entregable la versión web, cada criterio de
[docs/11-checklist-verificacion.md](docs/11-checklist-verificacion.md) debe tener un
resultado observable. El equipo marca `[x]` solo lo que ha ejecutado y verificado.

### 11.1 Funcional · Operación

- [x] Registrar una placa por primera vez crea el vehículo y la factura de ingreso.
- [x] Registrar dos veces la misma placa con estadía activa devuelve `409`.
- [x] La placa se normaliza a mayúsculas sin espacios.
- [x] Una placa en minúsculas y con espacios encuentra la misma estadía.
- [ ] La factura de ingreso sale con barcode Code128 de la placa en mayúsculas.
- [x] Cotizar una salida **no** cierra la estadía.
- [x] Cotizar muestra importe, minutos y método de cobro.
- [ ] Un plan vigente da cotización 0 dentro de su horario.
- [ ] Fuera del horario permitido cobra la tarifa normal.
- [x] Cobrar cierra la estadía, registra el pago y emite el recibo a la vez.
- [ ] El recibo de salida tiene barcode, QR, términos y pie de la plantilla.
- [x] El efectivo recibido muestra el cambio en vivo mientras se teclea.
- [x] Efectivo insuficiente indica cuánto falta.
- [ ] CARD, TRANSFER y DIGITAL_WALLET rechazan el campo de efectivo.
- [ ] Referencia bancaria se guarda en transferencia.
- [x] Cobrar en efectivo sin turno abierto se rechaza.
- [ ] Los 7 esquemas de cobro producen los importes esperados.
- [ ] Anular un cobro devuelve la estadía a ACTIVE y deja el motivo.
- [x] Repetir la misma Idempotency-Key devuelve el mismo pago y no cobra dos veces.

**Prueba de transaccionalidad**

- [ ] Si falla la emisión del recibo, no queda el cobro.
- [ ] Si falla el cobro, la estadía sigue ACTIVE.
- [ ] 20 cobros simultáneos de la misma placa: uno gana, los demás `409`.
- [ ] Numeración de comprobantes concurrente: sin duplicados.

### 11.2 Funcional · Mensualidades

- [ ] Un cliente sin mensualidad aparece con estado SIN PLAN.
- [ ] Un plan vencido se muestra VENCIDA aunque la columna diga ACTIVE.
- [ ] La búsqueda funciona por nombre, documento, teléfono y placa.
- [ ] El filtro de estado acepta el código interno y la etiqueta en español.
- [ ] El filtro «sólo con saldo» deja fuera a quien ya pagó.
- [ ] Alta de cliente exige nombre y documento único.
- [ ] Alta de plan exige al menos una placa.
- [ ] Registrar una placa nueva la asocia al cliente.
- [ ] El horario permitido exige ambas horas o ninguna.
- [ ] Un horario que cruza medianoche se calcula bien.
- [ ] 31 de enero + 1 mes = 28 de febrero (29 en bisiesto).
- [ ] Renovar un plan vigente encadena al día siguiente del vencimiento.
- [ ] Renovar un plan vencido arranca hoy.
- [ ] La renovación crea el período y cobra en la misma transacción.
- [ ] Si el cobro de la renovación falla, no queda período creado.
- [ ] El saldo nunca es negativo.
- [ ] Los 4 métodos de pago funcionan en cobro y renovación.
- [ ] Cancelar conserva el historial de pagos.
- [ ] Las alertas muestran lo que está por vencer y lo vencido con saldo.

### 11.3 Funcional · Histórico

- [ ] Los 5 filtros funcionan sueltos y combinados.
- [ ] Sin rango de fechas devuelve sólo el día de hoy.
- [ ] desde > hasta devuelve `400`.
- [ ] Toda hora se muestra en hh:mm de 24 horas.
- [ ] Una estadía sin salida muestra — en la hora de salida.
- [x] El calendario acepta `2026-10-06`, `06/10/2026`, `06.10.2026` y `6-10-26`.
- [x] `6-10-26` se lee como 6 de octubre, no 26 de octubre.
- [x] El calendario tiene botón «Hoy».
- [x] El campo sigue aceptando escritura a mano.
- [ ] La reimpresión funciona desde la factura de ingreso y desde el recibo de salida.
- [ ] El límite de resultados avisa cuando se alcanza.

### 11.4 Funcional · Gráfico y dashboard

- [x] El gráfico devuelve 24 puntos, aunque el día esté vacío.
- [ ] Un día futuro devuelve cero en las 24 horas.
- [ ] Las franjas usan la hora local del sitio, no UTC.
- [ ] El detalle de una hora lista exactamente las placas que marca el gráfico.
- [ ] Un vehículo pagado que sigue dentro aparece en el detalle.
- [ ] La escala del eje se ajusta con patrón 1-2-3-5.
- [ ] Con pocos vehículos y 30 cupos la curva se ve (no aplastada).
- [ ] La capacidad aparece como línea de referencia.
- [ ] Pasar el ratón marca la hora.
- [ ] El clic abre el detalle de esa hora.
- [ ] El clic en el día lleva al histórico con el rango puesto.
- [x] Los nombres de día y mes salen en español.

### 11.5 Funcional · Comprobantes

- [x] La numeración es consecutiva por sede.
- [ ] Dos sedes empiezan su numeración aparte.
- [ ] Un EXIT exige la estadía asociada.
- [ ] La vista previa muestra exactamente lo que se va a imprimir.
- [ ] El PDF coincide con la vista previa.
- [ ] El PNG térmico sale en 58 y en 80 mm.
- [x] El QR apunta a una URL pública que resuelve sólo con su token.
- [ ] Un token inventado da `404`.
- [ ] Reimprimir incrementa el contador y deja auditoría.
- [ ] El comprobante sale con el NIT y la dirección de la plantilla activa.
- [ ] Los términos y el pie salen de la plantilla, no están fijos en el código.

### 11.6 Funcional · Caja

- [x] Abrir turno guarda el monto inicial.
- [x] No se pueden abrir dos turnos para el mismo usuario.
- [x] El esperado del turno suma sólo los cobros en efectivo.
- [x] Cerrar guarda esperado, contado y diferencia.
- [ ] Una diferencia negativa se muestra con el signo correcto.
- [ ] La lista de turnos abiertos filtra por usuario y por todos.

### 11.7 Funcional · Configuración

- [ ] Crear una tarifa no altera el cobro de una estadía que ya usa la anterior.
- [ ] Crear un operador lo puede hacer un administrador.
- [ ] Crear un super administrador sólo lo puede hacer un super administrador.
- [ ] Un administrador no puede cambiar la contraseña de un super administrador.
- [ ] Desactivar un usuario invalida sus sesiones al instante.
- [ ] Nadie puede desactivar su propia cuenta.
- [ ] Los datos fiscales sólo los cambia el super administrador.
- [ ] La plantilla sólo la cambia el super administrador.
- [ ] El cambio de datos y de plantilla queda auditado.

### 11.8 Seguridad

- [x] El token de sesión nunca aparece en localStorage, en una URL ni en un registro.
- [ ] La cookie tiene HttpOnly, Secure y SameSite.
- [x] El frontend no puede leer la cookie desde JavaScript.
- [ ] El hash de una contraseña nunca sale de la base ni de una respuesta.
- [ ] Un perfil de scrypt manipulado en la base es rechazado en el login.
- [ ] Un OPERATOR recibe 403 en mensualidades, histórico y configuración.
- [ ] Un ADMIN recibe 403 en datos fiscales, plantillas y reportes.
- [ ] Un usuario desactivado pierde el acceso en la siguiente petición.
- [x] La recuperación de administrador no está expuesta por HTTP.
- [x] POST /api/auth/first-user responde 409 si ya hay usuarios.
- [ ] Los intentos de login fallidos quedan auditados.
- [ ] Cambiar la contraseña propia conserva la sesión actual y revoca las demás.
- [ ] audit_logs.ip_address se llena.
- [ ] before_data y after_data no contienen contraseñas ni tokens.
- [ ] El perfil de scrypt de la tabla es el vigente.

### 11.9 Hora del sistema

**Verificación del reloj desactivada.** En la versión web la única autoridad de tiempo es
el servidor, así que la cotización y el cobro ya no comprueban la deriva del reloj ni
bloquean con `reloj_no_confiable` (en la práctica bloqueaba los cobros tras cada reinicio
del equipo). La tarjeta «Estado del reloj» del dashboard y la pestaña «Reloj» de
Configuración se retiraron. El módulo `time_integrity.py` y las rutas `/api/clock/*`
siguen en el código pero ya no intervienen en ningún flujo.

- [x] Cotizar y cobrar funcionan aunque el servidor se haya reiniciado.
- [x] El frontend no calcula ni valida hora alguna.

### 11.10 Reportes y exportaciones

- [ ] Un operador ve el dashboard pero no el consolidado.
- [ ] Un administrador ve el dashboard pero recibe 403 en el consolidado.
- [x] El CSV abre en Excel con los acentos correctos.
- [x] El JSON devuelve los importes como cadena.
- [x] El XLSX de resumen tiene la hoja de totales.
- [x] El XLSX completo tiene 5 hojas y 2 gráficos.
- [ ] El gráfico del XLSX coincide con el del dashboard.
- [x] El PDF tiene la tabla con el estilo de la marca.
- [ ] Los totales de las 5 exportaciones cuadran entre sí.

### 11.11 Interfaz

- [x] El login muestra el fondo y el cristal de la marca.
- [ ] El cristal se ve bien en modo claro y en modo oscuro.
- [ ] El modo elegido se recuerda al recargar.
- [x] La tarjeta de login no tapa la marca del fondo.
- [x] Los nombres de días y meses están en español en toda la interfaz.
- [x] Todas las horas están en hh:mm.
- [x] Los importes usan formato colombiano ($45.000,00).
- [ ] El botón de imprimir está deshabilitado cuando no hay selección.
- [x] Cada lista tiene estado de carga y estado vacío.
- [x] El botón de calendario es visible junto a cada campo de fecha.
- [x] El foco es visible en todos los controles.
- [ ] Toda la aplicación se puede usar sólo con el teclado.
- [x] Los diálogos se cierran con Escape.

### 11.12 Responsive

| Ancho | Comprobación | Hecho |
|-------|--------------|-------|
| 1920 | La barra lateral no se estira; el contenido se centra | [ ] |
| 1440 | Diseño de referencia, sin scrolls horizontales | [ ] |
| 1280 | Todo visible sin recortar | [ ] |
| 1080 | Mínimo original: nada queda inaccesible | [ ] |
| 768 | La barra lateral pasa a cajón; las tablas con scroll | [ ] |
| 390 | Navegación inferior; formularios en una columna; cobro usable con el pulgar | [ ] |

### 11.13 Accesibilidad

- [ ] Contraste ≥ 4,5:1 en texto normal.
- [ ] Contraste ≥ 3:1 en texto grande y bordes de campos.
- [ ] Navegación completa por teclado, incluidos los diálogos.
- [x] Cada campo tiene su `<label>` asociado.
- [x] El cambio de la cotización se anuncia (aria-live).
- [x] El resultado del cobro se anuncia (aria-live).
- [x] Los errores tienen texto, no sólo color.
- [ ] Objetivos táctiles de 44 × 44 px en móvil.
- [x] prefers-reduced-motion respetado.
- [ ] El orden de tabulación sigue el orden visual.

### 11.14 Rendimiento

| Medida | Objetivo | Resultado |
|--------|----------|-----------|
| Primera carga del login | < 2 s | |
| Listado del histórico (500 filas) | < 800 ms | |
| Cotización de salida | < 300 ms | |
| Cobro de salida | < 1 s | |
| Exportación XLSX completa | < 10 s | |
| Gráfico de ocupación | < 300 ms | |

- [ ] Las seis medidas dentro del objetivo.
- [ ] El cálculo de tarifa no está cacheado.

### 11.15 Datos y migración

- [ ] receipt_counters = máximo histórico + 1.
- [ ] Total cobrado idéntico al original al centavo.
- [ ] Total en efectivo y cambios idénticos.
- [ ] Total por turno de caja cerrado idéntico.
- [ ] Las contraseñas existentes siguen funcionando.
- [ ] El histórico, el dashboard y el XLSX muestran las mismas cifras que el escritorio.

### 11.16 Despliegue

- [ ] deploy/.env.production no está versionado.
- [ ] Ninguna variable VITE_ contiene un secreto.
- [ ] HTTPS activo; cookie con Secure.
- [ ] PARKIUM_ORIGENES_PERMITIDOS no incluye *.
- [ ] PARKIUM_URL_PUBLICA_BASE es el dominio real.
- [ ] PARKIUM_PROVEEDOR_FACTURACION=DISABLED.
- [ ] alembic current coincide con head.
- [ ] /api/health responde 200 desde fuera.
- [ ] Sin acceso directo a PostgreSQL desde Internet.
- [ ] Copia de seguridad automática funcionando.
- [ ] Restauración probada de verdad.
- [ ] Los registros llegan al sistema centralizado.

### 11.17 Facturación electrónica

- [x] PARKIUM_PROVEEDOR_FACTURACION=DISABLED.
- [x] Ninguna pantalla presenta la factura interna como documento electrónico.
- [ ] issue_receipt_invoice falla con un mensaje explicativo.
- [ ] La tabla electronic_invoices está vacía.

### 11.18 Lo que no se puede verificar aquí

Depende de hardware o decisión externa; quedar explícitamente pendientes, no dados por
buenos: impresora térmica ESC/POS, ancho real del rollo, dialecto ESC/POS, calidad de
impresión, lectura del QR impreso, cumplimiento fiscal, autorización del Proveedor
Tecnológico, tiempo real de migración, red intermitente, capacitación del operador.

> Nadie debe firmar la salida de la versión web sin resolver la primera fila.
> Una impresora que no imprime es un sistema de cobro inservible.

### 11.19 Módulo multi-tenant y plataforma

**Aislamiento** (verificado por `backend/scripts/smoke_multi_tenant.py`, 29/29 OK):

- [x] Dos tenants creados por la API quedan totalmente separados.
- [x] La misma placa puede existir en dos tenants sin colisión (`UNIQUE(tenant_id, plate)`).
- [x] El recibo de un tenant responde `404` cuando se pide con la sesión de otro.
- [x] Un usuario de tenant recibe `403` en `/api/platform/*`.
- [x] El administrador de plataforma es rechazado en las rutas operativas.

**Cuotas:**

- [x] Exceder `max_sites` responde `409` con codigo `limite_plan_alcanzado`.
- [x] Exceder `max_users` responde `409` con codigo `limite_plan_alcanzado`.
- [x] NIT inválido responde `400` con codigo `validacion`.

**Suspensión:**

- [x] Suspender requiere el motivo (vacío → error).
- [x] Con el cliente suspendido, el login del tenant devuelve `403` con el mensaje exacto «Cuenta suspendida, contacta a soporte».
- [x] Las sesiones activas del tenant quedan revocadas (siguiente petición → `401`).
- [x] Los recibos públicos `/r/{token}` siguen respondiendo `200` con el cliente suspendido.
- [x] Reactivar repermitido el login; las sesiones antiguas siguen revocadas.

**Auditoría:**

- [x] Crear/suspender/reactivar cliente deja eventos `TENANT_CREATED` / `SUSPEND` / `REACTIVATE`.
- [x] El listado de auditoría acepta los filtros desde, hasta, acción y tenant_id.

**Frontend `/plataforma`** (verificado en Chromium contra el backend real, sin errores de consola):

- [x] Resumen, Clientes, Administrar cliente (4 pestañas) y Auditoría operables en el navegador.
- [x] El login redirige por rol: el administrador de plataforma entra a `/plataforma`.
- [ ] La creación de cliente y la suspensión/reactivación ejercitadas con clicks reales (crear tenants ya verificado por la API en el smoke; la UI sólo se comprobó en lectura).

---

## 8. Estado actual de la implementación

- **Backend:** completo (25 tablas, 10 routers, middleware de errores,
  caja con turnos, recibos con QR/Code128, comprobantes públicos `/r/{token}`,
  suscripciones con `_month_end`, reportes con **las 5 exportaciones** de docs/04 §4.9
  (`summary.csv` BOM, `summary.json`, `summary.xlsx`, `summary.pdf` con estilo de marca
  y `full.xlsx` con 5 hojas + 2 gráficos, vía `app/domain/exporters.py` + openpyxl),
  scripts de admin y smoke test. Prueba de humo aprobada: salud, login, entrada,
  duplicado 409, cotización, caja, cobro + idempotencia y dashboard.
  Las 5 exportaciones verificadas por HTTP con sesión (200, MIME y firma de archivo
  OK; 401 sin sesión). El corte `por_tarifa` se llena desde `parking_stays.tariff_plan_id`,
  que el cobro guarda con la tarifa aplicada (las estadías cobradas antes de este cambio
  no tienen tarifa asociada y no aparecen en ese corte).
- **Frontend:** Vite + React + TypeScript construido con el sistema de diseño de
  docs/06 (paleta claro/oscuro, sidebar 235px siempre oscura, login con cristal sobre
  `login_bg.jpg`, DatePicker con los 4 formatos, gráfico de ocupación 24 puntos,
  importes `$45.000,00` en es-CO). Páginas: Login, Dashboard, Operación, Histórico,
  Mensualidades (5 diálogos), Configuración (hasta 5 pestañas según rol), Reportes
  (sólo SUPERADMIN), Recuperación (documentada como no exponible por HTTP).
  **Módulo `/plataforma` (Fase 3):** juego de rutas separado sólo para
  `PLATFORM_ADMIN` con tema oscuro propio (`.pf`, acento morado, outline naranja):
  Resumen (KPIs + últimos clientes), Clientes (alta con primer admin y contraseña
  temporal de un solo uso, suspender/reactivar con Modal y motivo, filtro por
  estado), Administrar cliente (pestañas General / Sedes / Administradores / Plan
  y límites), Auditoría (tabla paginada con filtros desde/hasta/acción/tenant).
  El login redirige por rol: plataforma → `/plataforma`, tenant → `/`.
- **Compilación:** `tsc -b` y `vite build` pasan sin errores.
- **Auditoría UI/UX:** los 30 hallazgos aplicados y verificados en navegador (Edge headless
  contra una copia de la base): modales, DatePicker, sidebar colapsada, sin scroll
  horizontal a 1000/768/375 px, flujo de entrada → cobro y módulo de plataforma.
