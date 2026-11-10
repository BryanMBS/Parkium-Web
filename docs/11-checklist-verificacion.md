# 11 — Checklist de verificación

Comprobaciones **concretas y verificables** antes de publicar. Cada una tiene un
resultado esperado observable. Ninguna se da por buena sin ejecutarla.

---

## 11.1 Funcional · Operación

- [ ] Registrar una placa por primera vez crea el vehículo **y** la factura de ingreso.
- [ ] Registrar dos veces la misma placa con estadía activa devuelve `409`.
- [ ] La placa se normaliza a mayúsculas sin espacios.
- [ ] Una placa en minúsculas y con espacios encuentra la misma estadía.
- [ ] La factura de ingreso sale con barcode Code128 de la placa en mayúsculas.
- [ ] Cotizar una salida **no** cierra la estadía.
- [ ] Cotizar muestra importe, minutos y método de cobro.
- [ ] Un plan vigente da cotización 0 dentro de su horario.
- [ ] Fuera del horario permitido cobra la tarifa normal.
- [ ] Cobrar cierra la estadía, registra el pago y emite el recibo **a la vez**.
- [ ] El recibo de salida tiene barcode, QR, términos y pie de la plantilla.
- [ ] El efectivo recibido muestra el cambio **en vivo** mientras se teclea.
- [ ] Efectivo insuficiente indica **cuánto falta**.
- [ ] `CARD`, `TRANSFER` y `DIGITAL_WALLET` rechazan el campo de efectivo.
- [ ] Referencia bancaria se guarda en transferencia.
- [ ] Cobrar en efectivo sin turno abierto se rechaza.
- [ ] Los 7 esquemas de cobro producen los importes esperados.
- [ ] Anular un cobro devuelve la estadía a `ACTIVE` y deja el motivo.
- [ ] Repetir la misma `Idempotency-Key` devuelve el mismo pago y no cobra dos veces.

### Prueba de transaccionalidad

- [ ] Si falla la emisión del recibo, **no queda el cobro**.
- [ ] Si falla el cobro, **la estadía sigue `ACTIVE`**.
- [ ] 20 cobros simultáneos de la misma placa: **uno gana**, los demás `409`.
- [ ] Numeración de comprobantes concurrente: **sin duplicados**.

---

## 11.2 Funcional · Mensualidades

- [ ] Un cliente **sin** mensualidad aparece con estado `SIN PLAN`.
- [ ] Un plan vencido se muestra `VENCIDA` aunque la columna diga `ACTIVE`.
- [ ] La búsqueda funciona por nombre, documento, teléfono y placa.
- [ ] El filtro de estado acepta el código interno y la etiqueta en español.
- [ ] El filtro «sólo con saldo» deja fuera a quien ya pagó.
- [ ] Alta de cliente exige nombre y documento único.
- [ ] Alta de plan exige al menos una placa.
- [ ] Registrar una placa nueva la asocia al cliente.
- [ ] El horario permitido exige ambas horas o ninguna.
- [ ] Un horario que cruza medianoche se calcula bien.
- [ ] 31 de enero + 1 mes = **28 de febrero** (29 en bisiesto).
- [ ] Renovar un plan **vigente** encadena al día siguiente del vencimiento.
- [ ] Renovar un plan **vencido** arranca hoy.
- [ ] La renovación crea el período **y** cobra en la misma transacción.
- [ ] Si el cobro de la renovación falla, **no queda período creado**.
- [ ] El saldo nunca es negativo.
- [ ] Los 4 métodos de pago funcionan en cobro y renovación.
- [ ] Cancelar conserva el historial de pagos.
- [ ] Las alertas muestran lo que está por vencer y lo vencido con saldo.

---

## 11.3 Funcional · Histórico

- [ ] Los 5 filtros funcionan sueltos y combinados.
- [ ] Sin rango de fechas devuelve sólo el día de hoy.
- [ ] `desde > hasta` devuelve `400`.
- [ ] Toda hora se muestra en `hh:mm` de 24 horas.
- [ ] Una estadía sin salida muestra `—` en la hora de salida.
- [ ] El calendario acepta `2026-10-06`, `06/10/2026`, `06.10.2026` y `6-10-26`.
- [ ] `6-10-26` se lee como **6 de octubre**, no 26 de octubre.
- [ ] El calendario tiene botón «Hoy».
- [ ] El campo sigue aceptando escritura a mano.
- [ ] La reimpresión funciona desde la factura de ingreso y desde el recibo de salida.
- [ ] El límite de resultados avisa cuando se alcanza.

---

## 11.4 Funcional · Gráfico y dashboard

- [ ] El gráfico devuelve **24 puntos**, aunque el día esté vacío.
- [ ] Un día futuro devuelve cero en las 24 horas.
- [ ] Las franjas usan la **hora local del sitio**, no UTC.
- [ ] El detalle de una hora lista **exactamente** las placas que marca el gráfico.
- [ ] Un vehículo pagado que sigue dentro **aparece** en el detalle.
- [ ] La escala del eje se ajusta con patrón 1-2-3-5.
- [ ] Con pocos vehículos y 30 cupos la curva **se ve** (no aplastada).
- [ ] La capacidad aparece como línea de referencia.
- [ ] Pasar el ratón marca la hora.
- [ ] El clic abre el detalle de esa hora.
- [ ] El clic en el día lleva al histórico con el rango puesto.
- [ ] Los nombres de día y mes salen en **español**.

---

## 11.5 Funcional · Comprobantes

- [ ] La numeración es consecutiva **por sede**.
- [ ] Dos sedes empiezan su numeración aparte.
- [ ] Un `EXIT` exige la estadía asociada.
- [ ] La vista previa muestra exactamente lo que se va a imprimir.
- [ ] El PDF coincide con la vista previa.
- [ ] El PNG térmico sale en 58 y en 80 mm.
- [ ] El QR apunta a una URL pública que resuelve **sólo** con su token.
- [ ] Un token inventado da `404`.
- [ ] Reimprimir incrementa el contador y deja auditoría.
- [ ] El comprobante sale con el NIT y la dirección de la plantilla activa.
- [ ] Los términos y el pie salen de la plantilla, no están fijos en el código.

---

## 11.6 Funcional · Caja

- [ ] Abrir turno guarda el monto inicial.
- [ ] No se pueden abrir dos turnos para el mismo usuario.
- [ ] El esperado del turno suma sólo los cobros **en efectivo**.
- [ ] Cerrar guarda esperado, contado y diferencia.
- [ ] Una diferencia negativa se muestra con el signo correcto.
- [ ] La lista de turnos abiertos filtra por usuario y por todos.

---

## 11.7 Funcional · Configuración

- [ ] Crear una tarifa no altera el cobro de una estadía que ya usa la anterior.
- [ ] Crear un operador lo puede hacer un administrador.
- [ ] Crear un super administrador **sólo** lo puede hacer un super administrador.
- [ ] Un administrador no puede cambiar la contraseña de un super administrador.
- [ ] Desactivar un usuario **invalida sus sesiones al instante**.
- [ ] Nadie puede desactivar su propia cuenta.
- [ ] Los datos fiscales sólo los cambia el super administrador.
- [ ] La plantilla sólo la cambia el super administrador.
- [ ] El cambio de datos y de plantilla queda auditado.

---

## 11.8 Seguridad

- [ ] El token de sesión **nunca** aparece en `localStorage`, en una URL ni en un registro.
- [ ] La cookie tiene `HttpOnly`, `Secure` y `SameSite`.
- [ ] El frontend **no** puede leer la cookie desde JavaScript.
- [ ] El hash de una contraseña nunca sale de la base ni de una respuesta.
- [ ] Un perfil de scrypt manipulado en la base es **rechazado** en el login.
- [ ] Un `OPERATOR` recibe `403` en mensualidades, histórico y configuración.
- [ ] Un `ADMIN` recibe `403` en datos fiscales, plantillas y reportes.
- [ ] Un usuario desactivado pierde el acceso en la siguiente petición.
- [ ] La recuperación de administrador **no está expuesta** por HTTP.
- [ ] `POST /api/auth/first-user` responde `409` si ya hay usuarios.
- [ ] Los intentos de login fallidos quedan auditados.
- [ ] Cambiar la contraseña propia conserva la sesión actual y revoca las demás.
- [ ] `audit_logs.ip_address` se llena.
- [ ] `before_data` y `after_data` no contienen contraseñas ni tokens.
- [ ] El perfil de scrypt de la tabla es el vigente.

---

## 11.9 Seguridad del reloj

- [ ] Cada cotización y cada cobro ejecutan la verificación del reloj.
- [ ] Con el reloj del servidor desviado, ambos devuelven `400 reloj_no_confiable`.
- [ ] `last_trusted_utc` **no** avanza mientras la verificación no sea limpia.
- [ ] Una verificación externa correcta reancla el reloj y reactiva el cobro.
- [ ] Si la red no responde, la verificación local sigue siendo válida y el cobro **sigue**.
- [ ] La verificación externa no bloquea más de 6 segundos.
- [ ] Cada verificación queda en `clock_checks` con fuente y deriva.
- [ ] El frontend **no** calcula ni valida hora alguna.

---

## 11.10 Reportes y exportaciones

- [ ] Un operador ve el dashboard pero no el consolidado.
- [ ] Un administrador ve el dashboard pero recibe `403` en el consolidado.
- [ ] El CSV abre en Excel **con los acentos correctos**.
- [ ] El JSON devuelve los importes **como cadena**.
- [ ] El XLSX de resumen tiene la hoja de totales.
- [ ] El XLSX completo tiene **5 hojas y 2 gráficos**.
- [ ] El gráfico del XLSX coincide con el del dashboard.
- [ ] El PDF tiene la tabla con el estilo de la marca.
- [ ] Los totales de las 5 exportaciones cuadran entre sí.

---

## 11.11 Interfaz

- [ ] El login muestra el fondo y el cristal de la marca.
- [ ] El cristal se ve bien en modo claro **y** en modo oscuro.
- [ ] El modo elegido se recuerda al recargar.
- [ ] La tarjeta de login no tapa la marca del fondo.
- [ ] Los nombres de días y meses están en español en toda la interfaz.
- [ ] Todas las horas están en `hh:mm`.
- [ ] Los importes usan formato colombiano (`$45.000,00`).
- [ ] El botón de imprimir está deshabilitado cuando no hay selección.
- [ ] Cada lista tiene estado de carga y estado vacío.
- [ ] El botón de calendario es **visible** junto a cada campo de fecha.
- [ ] El foco es visible en todos los controles.
- [ ] Toda la aplicación se puede usar sólo con el teclado.
- [ ] Los diálogos se cierran con `Escape`.

---

## 11.12 Responsive

| Ancho | Comprobación |
|---|---|
| 1920 | La barra lateral no se estira; el contenido se centra |
| 1440 | Diseño de referencia, sin scrolls horizontales |
| 1280 | Todo visible sin recortar |
| 1080 | Mínimo original: nada queda inaccesible |
| 768 | La barra lateral pasa a cajón; las tablas con scroll |
| 390 | Navegación inferior; los formularios en una columna; **el cobro es usable con el pulgar** |

- [ ] Los 6 anchos probados.
- [ ] Ningún elemento esencial queda fuera de pantalla.

---

## 11.13 Accesibilidad

- [ ] Contraste ≥ 4,5:1 en texto normal.
- [ ] Contraste ≥ 3:1 en texto grande y en los bordes de los campos.
- [ ] Navegación completa por teclado, incluidos los diálogos.
- [ ] Cada campo tiene su `<label>` asociado.
- [ ] El cambio de la cotización se anuncia (`aria-live`).
- [ ] El resultado del cobro se anuncia (`aria-live`).
- [ ] Los errores tienen texto, no sólo color.
- [ ] Objetivos táctiles de 44 × 44 px en móvil.
- [ ] `prefers-reduced-motion` respetado.
- [ ] El orden de tabulación sigue el orden visual.

---

## 11.14 Rendimiento

| Medida | Objetivo | Resultado |
|---|---|---|
| Primera carga del login | < 2 s | |
| Listado del histórico (500 filas) | < 800 ms | |
| Cotización de salida | < 300 ms | |
| **Cobro de salida** | < 1 s | |
| Exportación XLSX completa | < 10 s | |
| Gráfico de ocupación | < 300 ms | |

- [ ] Las seis medidas dentro del objetivo.
- [ ] El cálculo de tarifa **no** está cacheado.

---

## 11.15 Datos y migración

- [ ] `receipt_counters` = máximo histórico + 1.
- [ ] Total cobrado idéntico al original **al centavo**.
- [ ] Total en efectivo y cambios idénticos.
- [ ] Total por turno de caja cerrado idéntico.
- [ ] Las contraseñas existentes siguen funcionando.
- [ ] El histórico, el dashboard y el XLSX muestran las mismas cifras que el escritorio.

---

## 11.16 Despliegue

- [ ] `deploy/.env.production` no está versionado.
- [ ] Ninguna variable `VITE_` contiene un secreto.
- [ ] HTTPS activo; cookie con `Secure`.
- [ ] `PARKIUM_ORIGENES_PERMITIDOS` no incluye `*`.
- [ ] `PARKIUM_URL_PUBLICA_BASE` es el dominio real (los QR del papel lo necesitan).
- [ ] `PARKIUM_PROVEEDOR_FACTURACION=DISABLED`.
- [ ] `alembic current` coincide con `head`.
- [ ] `/api/health` responde 200 desde fuera.
- [ ] Sin acceso directo a PostgreSQL desde Internet.
- [ ] Copia de seguridad automática funcionando.
- [ ] **Restauración probada de verdad.**
- [ ] Alerta de reloj sospechoso configurada.
- [ ] Los registros llegan al sistema centralizado.

---

## 11.17 Facturación electrónica

- [ ] `PARKIUM_PROVEEDOR_FACTURACION=DISABLED`.
- [ ] Ninguna pantalla presenta la factura interna como documento electrónico.
- [ ] `issue_receipt_invoice` falla con un mensaje explicativo.
- [ ] La tabla `electronic_invoices` está vacía.

---

## 11.18 Lo que no se puede verificar aquí

Estas comprobaciones dependen de hardware o de una decisión externa. Deben
quedar **explícitamente pendientes**, no dadas por buenas:

| Elemento | Por qué | Quién lo verifica |
|---|---|---|
| Impresora térmica ESC/POS | Requiere el equipo físico | Operaciones |
| Ancho real del rollo (58 / 80 mm) | Depende del modelo | Operaciones |
| Compatibilidad de ESC/POS | Cada fabricante tiene su dialecto | Operaciones |
| Calidad de impresión enicket de 58 mm | Visual | Operaciones |
| Lectura del QR impreso con varios lectores | El QR puede quedar pequeño | Operaciones |
| Cumplimiento fiscal y tributario | No es técnico | Dirección financiera |
| Autorización del Proveedor Tecnológico | No existe aún | Dirección |
| Tiempo real de la migración | Depende del volumen | Equipo técnico |
| Comportamiento con la red del local intermitente | Depende de la red | Operaciones |
| Capacitación del operador | Requiere personas | Operaciones |

> **Nadie debe firmar la salida de la versión web sin resolver la primera fila.**
> Una impresora que no imprime es un sistema de cobro inservible, por mucho que
> todo lo demás funcione.
### 11.19 M�dulo multi-tenant y plataforma

**Aislamiento** (verificado por backend/scripts/smoke_multi_tenant.py, 29/29 OK):

- [x] Dos tenants creados por la API quedan totalmente separados.
- [x] La misma placa puede existir en dos tenants sin colisi�n (UNIQUE(tenant_id, plate)).
- [x] El recibo de un tenant responde 404 cuando se pide con la sesi�n de otro.
- [x] Un usuario de tenant recibe 403 en /api/platform/*.
- [x] El administrador de plataforma es rechazado en las rutas operativas.

**Cuotas:**

- [x] Exceder max_sites responde 409 con c�digo limite_plan_alcanzado.
- [x] Exceder max_users responde 409 con c�digo limite_plan_alcanzado.
- [x] NIT inv�lido responde 400 con c�digo validacion.

**Suspensi�n:**

- [x] Suspender exige el motivo (vacio significa error).
- [x] Con el cliente suspendido el login devuelve 403 con el mensaje exacto de suspensi�n (soporte).
- [x] Las sesiones activas del tenant quedan revocadas (la siguiente petici�n responde 401).
- [x] Los recibos p�blicos /r/{token} siguen respondiendo 200 con el cliente suspendido.
- [x] Reactivar repermite el login; las sesiones antiguas siguen revocadas.

**Auditor�a:**

- [x] Crear/suspender/reactivar cliente deja eventos TENANT_CREATED / SUSPEND / REACTIVATE.
- [x] El listado acepta los filtros desde, hasta, acci�n y tenant_id.

**Frontend /plataforma** (verificado en Chromium contra el backend real, sin errores de consola):

- [x] Resumen, Clientes, Administrar cliente (4 pesta�as) y Auditor�a operables en el navegador.
- [x] El login redirige por rol: el administrador de plataforma entra a /plataforma.
- [ ] La creaci�n de cliente y la suspensi�n/reactivaci�n ejercitadas con clics reales (la UI se comprob� en lectura; los flujos ya pasan por la API en el humo).
