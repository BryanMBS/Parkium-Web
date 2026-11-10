# 12 — Preguntas abiertas

Todo lo que **no** se pudo determinar leyendo el código, o que depende de una
decisión del negocio. Nada aquí se ha supuesto en ningún otro documento.

Cada pregunta indica su impacto, las opciones con su valoración y una
recomendación. **El sprint 0 consiste en resolverlas.**

---

## 12.1 ¿Cuál es la fuente de verdad del esquema: SQLite o MySQL?

### El hecho verificado

El proyecto tiene **dos** definiciones del esquema que **no coinciden**:

| Fuente | Archivo | Motor | Volumen |
|---|---|---|---|
| Esquema de desarrollo | `app/data/temporary_database.py` | SQLite | 32 KB, 25 tablas, `SCHEMA_VERSION = 3` |
| Esquema de producción | `sql/001_initial_schema.sql` + `002` + `003` | MySQL 8 | 17,6 + 7 + 5,3 KB |
| Mapeo ORM | `app/data/models.py` | SQLAlchemy | 33,8 KB, aparentemente sin usar por la lógica |

El módulo `temporary_database.py` dice en su docstring que «no sustituye el
esquema MySQL de producción». Y `sql/` está comentado como «la base de la
variante multi-sede». **Ninguna de las dos está marcada como la definitiva.**

### Impacto

Alto. Define el motor de la base, el dialecto SQL, el tipo de las columnas y el
formato de las migraciones. Decidir mal obliga a rehacer la revisión `0001`.

### Opciones

| Opción | Ventaja | Desventaja |
|---|---|---|
| **A — SQLite como referencia** | Es lo que ejecuta el sistema hoy; el código Python usa `sqlite3` | `julianday()`, `INSERT OR IGNORE` y `PRAGMA` no existen en PostgreSQL |
| B — MySQL 8 como referencia | Ya hay un esquema completo versionado para él | El código Python habría que adaptarlo igual, y `julianday()` tampoco existe en MySQL |
| **C — PostgreSQL como referencia** | Tipos correctos (`TIMESTAMPTZ`, `BOOLEAN`, `NUMERIC`), restricciones `CHECK` reales, mejor para concurrencia | Hay que escribir el esquema desde cero |

### Recomendación

**C — PostgreSQL**, tomando `app/data/temporary_database.py` como referencia de
contenido (es lo que realmente se usa) y `sql/001_initial_schema.sql` como
comprobación de que no falte ninguna tabla. Ver
[03-esquema-base-datos.md](03-esquema-base-datos.md) §3.9 para la traducción
tipada completa.

Motivo: los dos esquemas existentes están pensados para desarrollo y para
«multi-sede», ninguno es el destino final de la web, y PostgreSQL resuelve el
problema de `TEXT` con fechas que ambos tienen. Si el negocio ya tiene
infraestructura MySQL, la opción B es defendible con los mismos ajustes tipados.

### Quién decide

Equipo técnico, con el dato de si ya existe un servidor de base de datos en la
organización.

---

## 12.2 ¿Cómo se recupera la contraseña del administrador si nadie puede entrar?

### El hecho verificado

`reset_administrator_password` restablece la contraseña de cualquier cuenta
`ADMIN` o `SUPERADMIN` **sin exigir la anterior**, reactiva la cuenta y revoca
sus sesiones. La interfaz lo expone como `_show_recovery`. Se invoca en
`app/services/authentication.py` y `app/ui/main_window.py`.

Es aceptable en escritorio: quien tiene acceso físico al equipo ya tiene acceso
a todo lo demás. **En una web, exponerlo sería una escalada de privilegios
completa.**

### Impacto

**Crítico.** Si se expone sin más, cualquiera que encuentre la ruta puede tomar
el control de la instalación.

### Opciones

| Opción | Descripción | Requiere | Valoración |
|---|---|---|---|
| **A — No exponer** | Script de consola del servidor | Acceso al servidor | **Recomendada** |
| B — Correo al super administrador | Enlace de un solo uso con caducidad corta | **Correo saliente, que el proyecto no tiene** | Viable, hay que construirlo |
| C — Clave de rescate | Frase maestra en variable de entorno + código de un solo uso | Gestión de la frase | Viable y sin correo |
| D — Preguntas de seguridad | Respuestas del usuario | Ninguna útil | **Descartada**: no es seguridad |

### Recomendación

**A**, con un procedimiento documentado de rescate. Si el negocio exige que
cualquier administrador pueda recuperarse sin ayuda técnica, **C** como
complemento, con la frase maestra en el gestor de secretos del servidor y
rotación documentada.

### Relacionado

La contraseña del **primer** super administrador también cambia de naturaleza: hoy
es un asistente (`_show_first_run`), en web será un script de despliegue
(`scripts/create_first_admin.py`).

### Quién decide

Responsable de seguridad, con el negocio.

---

## 12.3 ¿Hay que imprimir en una impresora térmica ESC/POS?

### El hecho verificado

`app/services/printing.py` usa `pywin32` para enviar texto ESC/POS al spooler de
Windows. Además genera PNG monocromático para 58 y 80 mm
(`render_receipt_image`). **El original no pudo verificarse con una impresora
real**: el equipo de desarrollo no tenía una, y así consta en la documentación
del proyecto.

### Impacto

**Alto.** Una app de cobro sin impresión es un problema operativo, no un
detalle de interfaz. Y cada fabricante de impresora usa un dialecto ESC/POS
distinto.

### Opciones

| Opción | Descripción | Consecuencia técnica |
|---|---|---|
| A — Sólo navegador | `window.print()` con CSS `@page` | No requiere nada del servidor. Sale por cualquier impresora, incluida una térmica de 58 mm si el driver está instalado |
| B — Navegador **+** ESC/POS en el servidor | Lo anterior, más el spooler | Requiere el servidor en Windows con `pywin32` |
| C — Impresora de red dedicada | El servidor habla con la impresora por IP | Hay que conocer el modelo y su protocolo |

### Recomendación

**A como base**, que es lo que funciona en cualquier caso, y **B como
complemento** si se confirma que hay una impresora ESC/POS que debe seguir
usándose.

**Pero hay que responder antes dos preguntas que el código no puede contestar:**

1. ¿Existe físicamente una impresora térmica en el local? **No se puede asumir.**
2. Si existe, ¿cuál es su marca y modelo? **El dialecto ESC/POS depende del
   modelo**, y sin eso, `build_escpos_payload` es una conjetura.

> El proyecto original arrastra esta limitación desde el principio. La web no
> empeora el problema, pero tampoco lo resuelve sin información del negocio.

### Quién decide

Operaciones, con una respuesta sobre el equipo físico.

---

## 12.4 ¿Se activa la facturación electrónica?

### El hecho verificado

Existe el contrato `InvoiceProvider`, el registro de proveedores,
`build_request`, `issue_receipt_invoice` e `invoice_status`, y la tabla
`electronic_invoices` está en el esquema. Pero:

- El proveedor por defecto es **`DisabledProvider`**, que **falla siempre**.
- La variable es `PARKIUM_EINVOICE_PROVIDER=DISABLED`.
- En el esquema de desarrollo la tabla está **vacía**.
- El texto del proyecto es explícito: no activar ni simular.

**La factura de ingreso y el recibo de salida son documentos internos.** No son
facturación electrónica y no deben presentarse como tales.

### Impacto

Alto si se activa sin proveedor. La web no cambia nada de esto: el módulo ya
está diseñado para estar desactivado.

### Recomendación

**No activarlo en la versión web.** Es una decisión de negocio y de cumplimiento
legal que requiere un **Proveedor Tecnológico autorizado**, y eso no se resuelve
por código.

La web debe:

1. Mantener `PARKIUM_EINVOICE_PROVIDER=DISABLED`.
2. Dejar el contrato `InvoiceProvider` intacto para que activarlo más adelante sea
   un cambio de configuración, no de desarrollo.
3. **No** simular ningún estado de autorización.
4. Conservar la tabla `electronic_invoices` aunque quede vacía.

### Si el negocio insiste

Entonces hay que añadir, como alcance nuevo y aparte:

| Elemento | Detalle |
|---|---|
| Proveedor | Integración con un Proveedor Tecnológico concreto |
| Firma digital | Certificate de la empresa |
| CUFE | Asignado por el proveedor |
| Numeración | Secuencial autorizada, por sede |
| Contingencia | Qué ocurre si el proveedor no responde |
| Cumplimiento | Firma del responsable tributario |

Eso es un proyecto **nuevo**, no una tarea de esta versión.

### Quién decide

Dirección financiera y dirección jurídica. **No es una decisión técnica.**

---

## 12.5 ¿Se migran las fechas a `TIMESTAMPTZ` o se dejan en `TEXT`?

### El hecho verificado

Todas las marcas de tiempo del esquema están como `TEXT` con formato ISO-8601.
Funciona porque ese formato se ordena lexicográficamente, pero impide
restricciones `CHECK` e índices temporales fiables. Está descrito en
[03-esquema-base-datos.md](03-esquema-base-datos.md) §3.9.3.

### Impacto

Medio. Es la diferencia entre una base que aguanta auditoría y una que hay que
reescribir.

### Opciones

| Opción | Descripción | Consecuencia |
|---|---|---|
| **A — `TIMESTAMPTZ`** | Migrar en la revisión `0002` | Hay que adaptar `julianday()` y el acceso por tipo |
| B — Dejar `TEXT` | Portar tal cual | Todo el SQL funciona por comparación de cadena; **nunca** con `<`/`>` sobre otro tipo |
| C — `TIMESTAMP` sin zona | Un punto medio que no funciona | **Descartada**: la zona del sitio es `America/Bogota` y el horario de verano complica |

### Recomendación

**A.** El proyecto ya tiene el concepto de «fecha local del sitio»
(`today_for_site`, `_hora_local_utc`, `utc_bounds_for_local_range`), es decir,
**ya piensa en zonas horarias**. Guardar en texto lo contradice.

### Quién decide

Equipo técnico. La recomendación es clara y no requiere negocio.

---

## 12.6 ¿Una zona horaria o varias sedes?

### El hecho verificado

`parking_sites.timezone` **existe como columna** con valor por defecto
`America/Bogota`, y `today_for_site` la consulta. `DEFAULT_SITE_ID = 1` y la
semilla inserta **una** sede.

### Impacto

Medio. Si el sistema es de un solo local (lo sugiere todo el diseño), la columna
es una comodidad. Si crece a varias sedes en zonas distintas, hay que revisar
los índices, el corte del día local y los reportes.

### Opciones

| Opción | Descripción |
|---|---|
| **A — Una sede** | Ignorar la columna y fijar `America/Bogota` en configuración |
| B — Varias sedes, misma zona | La columna se lee siempre, pero el valor es el mismo |
| C — Varias sedes, zonas distintas | El día local de cada reporte se calcula con su zona |

### Recomendación

**A**, porque es lo que el sistema es hoy. **Dejar la columna y la lectura por
sede** (que es como está escrito el código) para que activar la opción C más
adelante no exija un rediseño.

**Pregunta al negocio:** ¿el sistema es para un local o para una cadena? De eso
depende todo el modelo de reportes.

### Quién decide

Negocio.

---

## 12.7 ¿En qué formato se imprimen los importes?

### El hecho verificado

El original imprime con `f"{valor:,.2f}"`, que da **`$45,000.00`**: separador de
millas con coma y punto decimal. El sistema trabaja en pesos colombianos, donde
lo habitual es **`$45.000,00`**.

### Impacto

Bajo, pero visible en cada comprobante.

### Opciones

| Opción | Descripción | Valoración |
|---|---|---|
| **A — Colombiano** `$45.000,00` | Es lo que espera el operador | **Recomendada** |
| B — Inglés `$45,000.00` | Idéntico al original | Paridad visual, no de negocio |

### Recomendación

**A.** Es una diferencia deliberada y deseable: paridad funcional **no** significa
paridad de un formato que es un error desde el punto de vista del usuario local.

> Lo que **no** se negocia: los importes viajan como **cadena decimal** en JSON.
> Ver §6.12 de [06-sistema-diseno.md](06-sistema-diseno.md).

### Quién decide

Operaciones. Es una pregunta de cinco segundos y evita reprintar plantillas.

---

## 12.8 ¿El historial de auditoría se migra completo?

### El hecho verificado

`audit_logs` puede tener miles de filas y contiene datos personales en
`before_data` / `after_data`. `ip_address` está disponible pero **sin usar**.

### Impacto

Medio. Afecta al volumen de la migración y al tratamiento de datos personales.

### Recomendación

**Migrar los últimos 6 meses**; lo anterior, sólo si el negocio exige
trazabilidad completa y lo firma por escrito. En la web, `ip_address` **sí** debe
llenarse: el proxy ya está configurado para ello en
[08-configuracion-despliegue.md](08-configuracion-despliegue.md).

### Quién decide

Responsable de datos, con el negocio.

---

## 12.9 ¿Se conserva `parking_zones` y `parking_spaces`?

### El hecho verificado

Ambas tablas existen, con sus claves foráneas y sus índices, y `parking_stays`
tiene `space_id`. **Sin embargo, la interfaz actual no las usa**: el operador
registra una placa, no un cupo. La ocupación se cuenta como estadías activas.

### Impacto

Bajo. Son tablas para una funcionalidad que no está construida.

### Opciones

| Opción | Descripción |
|---|---|
| **A — Crearlas y no usarlas** | Deja el esquema fiel al original |
| B — Moverlas a una migración posterior | Más limpio, pero se aparta del original |

### Recomendación

**A.** Crearlas sin variantes. Si algún día se asignan cupos, la estructura ya
está; si no, sobran dos tablas vacías. Es el coste más bajo de la fidelidad.

### Quién decide

Equipo técnico. No requiere negocio.

---

## 12.10 ¿Cómo se resuelve la caída de la fuente de hora externa?

### El hecho verificado

`time_integrity._network_reference` consulta la cabecera `Date` de un servidor
externo, **en un hilo con espera máxima**, porque la resolución de nombres no
respeta el timeout de `urlopen` y congelaba la interfaz. La URL por defecto es
`https://www.google.com/generate_204`.

### Impacto

Medio. Si la red del local se cae con frecuencia, la verificación externa
falla y hay que saber qué pasa.

### Opciones

| Opción | Descripción |
|---|---|
| **A — Continuar con la verificación local** | La verificación contra el reloj del servidor sigue siendo válida; sólo no hay contraste externo. **Es el comportamiento actual** |
| B — Bloquear el cobro si no hay red | Un corte de internet detendría el parqueadero. **Incorrecto** |
| C — Varias fuentes de respaldo | Más robustez ante bloqueos de un único proveedor |

### Recomendación

**A**, que es lo que ya hace el original y lo correcto: el parqueadero no puede
dejar de funcionar porque se cayó el internet. Añadir **C** si en el local se
ha observado que un único proveedor falla a menudo.

**Pregunta al negocio:** ¿hay algún proveedor de hora bloqueado en su red?

### Quién decide

Equipo técnico, con información de operaciones sobre la red del local.

---

## 12.11 ¿Cuál es el volumen real de datos?

### El hecho verificado

No hay ningún dato de producción en el proyecto. La base de desarrollo está
vacía o con datos de prueba.

### Impacto

Medio. Condiciona el plan de índices, el tiempo de las exportaciones y la
viabilidad de la Fase 1 de convivencia.

### Preguntas

| Pregunta | Para qué |
|---|---|
| ¿Cuántas estadías al día? | Dimensiona el histórico |
| ¿Cuántos registros tiene hoy la base? | Decide el tiempo de migración |
| ¿Cuántos usuarios? | Dimensiona la sesión y el ancho de banda |
| ¿Se conservarán los comprobantes impresos físicos? | Puede exigir tabla de archivo |
| ¿El histórico debe llegar a los 5 años o es ilimitado? | Decide el particionado |

### Recomendación

**Pedir un exporting de la base actual antes de empezar la migración.** Sin ese
dato, cualquier estimación de volumen es una suposición.

### Quién decide

Operaciones y equipo técnico.

---

## 12.12 Resumen: qué bloquea qué

| # | Pregunta | Bloquea | Sprint |
|---|---|---|---|
| 12.1 | Motor de la base | Todo el backend | 1 |
| 12.2 | Recuperación de administrador | Login y despliegue | 2 |
| 12.3 | Impresora térmica | Impresión | 4 |
| 12.4 | Facturación electrónica | Nada: se mantiene desactivada | — |
| 12.5 | `TIMESTAMPTZ` | La migración `0002` | 1 |
| 12.6 | Una o varias sedes | Reportes | 9 |
| 12.7 | Formato de importes | Plantilla del comprobante | 4 |
| 12.8 | Auditoría completa | Migración | 12 |
| 12.9 | Zonas y cupos | Nada: se crean sin usar | 1 |
| 12.10 | Caída de la fuente de hora | Nada: hay comportamiento por defecto | 5 |
| 12.11 | Volumen de datos | Estimaciones y migración | 0 |
| 12.12 | — | — | — |

**Sólo dos bloquean el inicio:** el motor de la base (12.1) y el volumen real
(12.11). Las demás se pueden decidir en paralelo, salvo 12.2, que bloquea el
login y conviene resolver antes del sprint 2.