# 01 — Matriz de paridad funcional

Cada fila es una funcionalidad **verificada en el código original** con su
equivalente web. Estado:

- **Idéntica** — mismo comportamiento, misma regla de negocio, cambia el canal.
- **Adaptada** — mismo objetivo, distinto mecanismo por cambio de plataforma.
- **No portable** — requiere revisión de negocio antes de decidir.

---

## 1.1 Trazabilidad: módulo → archivo fuente → funcionalidad

### Autenticación y acceso

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Cuentas | `app/services/authentication.py` | `create_first_administrator`, `create_user`, `list_users`, `set_user_active`, `change_user_password`, `change_own_password`, `reset_administrator_password` |
| Sesiones | `app/services/authentication.py` | `authenticate` (12 h), `validate_session`, `logout`, `cleanup_expired_sessions`, `has_users` |
| Roles | `app/services/authentication.py` | `require_role`, `require_admin`, `require_superadmin`, `is_superadmin`, `role_label` |
| Hash | `app/services/authentication.py` | `hash_password` / `verify_password` con **scrypt** (N=16384, r=8, p=1) |
| Login (UI) | `app/ui/main_window.py` | `_show_login`, `_login`, `_show_recovery`, `_complete_recovery`, `_show_first_run`, `_complete_first_run` |
| Recuperación | `app/ui/main_window.py` | `_show_recovery` (restablece admin local) |

### Operación de parqueo

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Entrada | `app/services/parking_operations.py` | `register_entry` (crea vehículo si es primera visita + factura de ingreso), `find_active_stay` |
| Cotización | `app/services/parking_operations.py` | `quote_exit`, `_quote_for_row` |
| Cobro | `app/services/parking_operations.py` | `collect_payment` (transaccional: cobro + cierre + recibo), `void_payment` |
| Ocupación | `app/services/parking_operations.py` | `occupancy` → `OccupancySnapshot(total_capacity, occupied, available, by_vehicle_type)` |
| Tarifas | `app/services/parking_operations.py` | `configure_tariff`, `active_tariffs`, `calculate_tariff` |
| Cobro (UI) | `app/ui/main_window.py` | `_show_operations`, `_register_entry`, `_quote`, `_collect`, `_toggle_cash_fields`, `_update_change` |

### Comprobantes e impresión

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Emisión | `app/services/receipts.py` | `next_receipt_number`, `issue_receipt`, `get_receipt`, `reprint_receipt` |
| Datos | `app/services/receipts.py` | `receipt_details`, `receipt_details_for_stay`, `latest_receipt_details` |
| Líneas | `app/services/receipts.py` | `receipt_lines`, `receipt_title`, `render_receipt_text` |
| Código | `app/services/receipts.py` | `barcode_value` (Code128 de la placa), `write_barcode_png`, `write_qr_png` |
| Documentos | `app/services/receipts.py` | `render_receipt_image` (PNG térmico 58/80 mm), `write_receipt_pdf`, `save_receipt_artifacts` |
| Reimpresión | `app/services/receipts.py` | `reprint_receipt_for_user` (valida rol + auditoría) |
| Impresora | `app/services/printing.py` | `build_escpos_payload`, `print_thermal_receipt`, `prepare_thermal_receipt`, `available_printers` |
| QR público | `app/services/receipt_web.py` | `ReceiptRequestHandler`, `start_background_server` → `/receipts/<token>` |
| Vista previa | `app/ui/main_window.py` | `_show_receipt_preview`, `_deliver_receipt`, `_print_preview`, `_open_file` |
| Fact. electrónica | `app/services/electronic_invoicing.py` | `InvoiceProvider` (Protocol), `DisabledProvider`, `register_provider`, `get_provider`, `build_request`, `issue_receipt_invoice`, `invoice_status` |

### Histórico

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Búsqueda | `app/services/history.py` | `search_history` (placa, rango, estado, tipo; límite 500), `stay_history` |
| Ocupación | `app/services/history.py` | `occupancy_by_hour` (24 puntos), `occupancy_detail`, `_stays_overlapping_day` |
| Historical (UI) | `app/ui/main_window.py` | `_show_history`, `_load_history`, `_reprint_from_history` |
| Calendario | `app/ui/calendar_popup.py` | `pick_date`, `attach_picker`, `_leer` |

### Mensualidades

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Clientes | `app/services/subscriptions.py` | `create_customer`, `customer_plans`, `customer_detail`, `customer_vehicles`, `attach_vehicle` |
| Plan | `app/services/subscriptions.py` | `create_subscription`, `create_agreement`, `cancel_subscription`, `find_valid_subscription` |
| Cartera | `app/services/subscriptions.py` | `portfolio_report`, `subscription_alerts`, `_effective_status` |
| Cobro | `app/services/subscriptions.py` | `pay_subscription`, `renew_subscription`, `_cash_movement`, `_open_shift`, `_month_end` |
| Vista | `app/ui/subscription_view.py` | `build_view` + 5 diálogos (alta cliente, alta plan, cobro, renovación, cancelación) |

### Caja

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Turnos | `app/services/cash.py` | `open_cash_shift`, `close_cash_shift`, `expected_cash`, `list_open_shifts`, `get_cash_shift` |

### Configuración y datos maestros

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Parqueadero | `app/services/site_settings.py` | `get_site_settings`, `update_site_settings` (NIT, nombre, dirección, teléfono) |
| Plantilla | `app/services/site_settings.py` | `get_receipt_template`, `update_receipt_template` (super admin) |
| Configuración (UI) | `app/ui/main_window.py` | `_show_admin` con 6 pestañas: Tarifas, Usuarios, Caja, Seguridad, Parqueadero, Plantilla |

### Reportes y exportación

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Consolidado | `app/services/reports.py` | `operation_summary`, `_require_report_access` (solo super admin) |
| Dashboard | `app/services/reports.py` | `dashboard_summary`, `_today_totals` (admin y operador) |
| Exportación | `app/services/reports.py` | `export_csv`, `export_json`, `export_excel`, `export_pdf` |
| XLSX completo | `app/services/exporters.py` | `export_full_excel` (5 hojas + 2 gráficos), `build_chart_model`, `daily_series` |

### Seguridad del reloj

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Verificación | `app/services/time_integrity.py` | `verify_clock`, `check_before_billing`, `clock_status_summary` |
| Ancla | `app/services/time_integrity.py` | `current_boot_id`, `_ensure_anchor`, `_drift_from_anchor`, `entry_monotonic_stamp`, `elapsed_minutes` |
| Red | `app/services/time_integrity.py` | `_network_reference` (cabecera HTTP `Date`, en hilo con timeout) |

### Dashboard

| Módulo | Archivo fuente | Funcionalidades |
|---|---|---|
| Tarjetas | `app/services/reports.py` | `dashboard_summary` → ocupación, ingresos del día, cupo disponible, salidas cobradas |
| Gráfico | `app/ui/occupancy_chart.py` | `build_chart`, `build_occupancy_panel`, `build_detail_view` |
| Vista | `app/ui/main_window.py` | `_show_dashboard`, `_add_occupancy_chart`, `_open_history_for_day`, `_verify_clock_online` |

---

## 1.2 Paridad por funcionalidad

### Autenticación

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Login usuario/contraseña | Idéntica | `POST /api/auth/login` | scrypt del lado servidor; nunca en el cliente |
| Sesión de 12 h | Idéntica | Token opaco en cookie `HttpOnly` + tabla `user_sessions` | Mantener `token_hash` (SHA-256), nunca el token en claro |
| Validación de sesión | Idéntica | Middleware de dependencia | Reutilizar `require_valid_session` |
| Rol y jerarquía | Idéntica | Middleware `require_role` | `SUPERADMIN` satisface cualquier rol (`_ROLE_IMPLICITS`) |
| Cambiar contraseña propia | Idéntica | `POST /api/auth/password` | — |
| Restablecer contraseña de otro | Idéntica | `PATCH /api/users/{id}/password` | Solo admin; nunca la del super admin |
| Recuperación local de admin | **No portable** | **No exponer por HTTP** | Hoy abre una ventana local sin sesión. Exponerla sería una escalada de privilegios. Ver [12](12-preguntas-abiertas.md) §2 |
| Activar/desactivar usuario | Idéntica | `PATCH /api/users/{id}/active` | Desactivar revoca sesiones |
| Contraseña del primer admin | Adaptada | Migración/`seed` en despliegue | Hoy es un asistente. En web: script de despliegue o variable de entorno |

### Operación

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Registrar entrada por placa | Idéntica | `POST /api/stays` | Idempotencia por placa: si ya hay activa, error explícito |
| Factura de ingreso | Idéntica | `POST /api/stays` devuelve el comprobante | Código interno, **no electrónica** |
| Verificar mensualidad vigente | Idéntica | Interno en `register_entry` | Usa `find_valid_subscription` |
| Cotizar salida | Idéntica | `GET /api/stays/{plate}/quote` | No cierra la estadía |
| Cobrar con método y vuelto | Idéntica | `POST /api/checkout` | **Transaccional**: cobro + cierre + recibo juntos |
| Efectivo recibido y cambio | Idéntica | Igual en el endpoint | Sólo `CASH` los registra |
| Validar turno de caja abierto | Idéntica | Igual | Un cobro en efectivo sin turno se rechaza |
| Bloqueo por reloj no confiable | Idéntica | Middleware obligatorio | Ver [05](05-modulos-implementacion.md) §7 |
| Anular cobro | Idéntica | `POST /api/payments/{id}/void` | Devuelve la estadía a `ACTIVE` |
| Ver impresoras de Windows | **No portable** | `GET /api/printers` desde el servidor | Ver [12](12-preguntas-abiertas.md) §3 |
| Imprimir ESC/POS | **Adaptada** | `POST /api/receipts/{id}/print` | El navegador imprime; el servidor conserva ESC/POS para el spooler |
| Vista previa del comprobante | Idéntica | Modal en el cliente | Debe permitir ver antes de imprimir |
| Abrir el archivo del comprobante | Adaptada | Descarga por HTTP | Hoy usa `os.startfile` |

### Comprobantes

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Numeración consecutiva | Idéntica | Interno | `receipt_counters` por sede, dentro de la transacción |
| Tipos ENTRY/EXIT/SUBSCRIPTION/ADJUSTMENT | Idéntica | Idéntico | Validado en `issue_receipt` |
| Barcode Code128 de la placa | Idéntica | Generación en servidor | `barcode_value` |
| QR del comprobante | Idéntica | URL absoluta | `receipt_query_url` |
| URL pública del QR | **Adaptada** | `GET /r/{token}` | Hoy `http.server` local; en web, ruta real con dominio |
| PNG térmico 58/80 mm | Idéntica | Servidor | `render_receipt_image` |
| PDF del comprobante | Idéntica | Servidor | `write_receipt_pdf` |
| Texto ESC/POS | Idéntica | Servidor | `render_receipt_text` |
| Reimpresión con contador | Idéntica | `POST /api/receipts/{id}/reprint` | Incrementa `reprint_count` y audita |
| Facturación electrónica | **No portable** | **Desactivada** | `DisabledProvider` falla siempre. Ver [12](12-preguntas-abiertas.md) §4 |

### Histórico

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Buscar por placa/rango/estado/tipo | Idéntica | `GET /api/history` | Límite 500 configurable |
| Horas en 24 h `hh:mm` | Idéntica | Igual | Formato del proyecto, no del navegador |
| Calendario de rango | Idéntica | Componente propio | Reutilizar la lógica de `calendar_popup._leer` |
| Reimprimir factura/recibo | Idéntica | Igual | — |
| Ocupación por hora (24 puntos) | Adaptada | `GET /api/occupancy/hourly` | Cálculo idéntico en el servidor |
| Detalle de una hora | Adaptada | `GET /api/occupancy/detail` | Gráfico y detalle **deben usar el mismo criterio** |
| Gráfico interactivo | Adaptada | Chart.js / Recharts | Escala de 1-2-3-5 por potencia de diez |
| Salto desde el gráfico al histórico | Idéntica | Navegación con estado | — |

### Mensualidades

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Alta de cliente con placas | Idéntica | `POST /api/customers` | Documento único |
| Registrar placas nuevas | Idéntica | `POST /api/customers/{id}/vehicles` | `attach_vehicle` |
| Alta de mensualidad | Idéntica | `POST /api/subscriptions` | Exige ≥ 1 placa |
| Listado por cliente con estado y saldo | Idéntica | `GET /api/customers/plans` | Estado derivado de la fecha |
| Estado `VIGENTE/POR VENCER/VENCIDA/CANCELADA/SIN PLAN` | Idéntica | Igual | `_effective_status` |
| Horario permitido 24 h | Idéntica | Igual | Ambas horas o ninguna |
| Cobrar saldo | Idéntica | `POST /api/subscriptions/{id}/pay` | Con cambio en efectivo |
| **Renovar** | Idéntica | `POST /api/subscriptions/{id}/renew` | Crea período + cobra en **una** transacción |
| Encadenar período | Idéntica | Igual | Si no ha vencido, arranca al día siguiente |
| Fin de mes real | Idéntica | `_month_end` | 31/01 + 1 mes = 28/02 (29 en bisiesto) |
| Cancelar plan | Idéntica | `POST /api/subscriptions/{id}/cancel` | Conserva historial |
| Alertas de cartera | Idéntica | `GET /api/subscriptions/alerts` | Por vencer / vencida con saldo |
| Convenios con descuento | Idéntica | `POST /api/agreements` | Porcentaje, fijo o tarifa especial |

### Caja

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Abrir turno con base | Idéntica | `POST /api/cash/shifts` | Un turno abierto por usuario y sede |
| Esperado del turno | Idéntica | `GET /api/cash/shifts/{id}/expected` | Suma de cobros en efectivo |
| Cerrar con conteo y diferencia | Idéntica | `POST /api/cash/shifts/{id}/close` | Guarda los tres importes |
| Listar turnos abiertos | Idéntica | `GET /api/cash/shifts` | — |

### Configuración

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| 6 pestañas por rol | Idéntica | Rutas por sección | Solo visibles si el rol las usa |
| Tarifas versionadas | Idéntica | `POST /api/tariffs` | 7 esquemas de cobro |
| Usuarios | Idéntica | `GET/POST /api/users` | Selector de rol en español |
| Caja | Idéntica | Ver sección Caja | — |
| Seguridad (reloj) | Adaptada | Ver [05](05-modulos-implementacion.md) §7 | El reloj monotónico no existe en el navegador |
| Datos del parqueadero (NIT) | Idéntica | `PATCH /api/site` | Solo super admin |
| Plantilla de factura | Idéntica | `PATCH /api/receipt-template` | Solo super admin, incluye términos y pie |

### Reportes

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Consolidado por rango | Idéntica | `GET /api/reports/summary` | Solo super admin |
| Dashboard del día | Idéntica | `GET /api/dashboard` | Admin y operador |
| Exportar CSV | Idéntica | `GET /api/reports/summary.csv` | UTF-8 con BOM |
| Exportar JSON | Idéntica | `GET /api/reports/summary.json` | Importes como texto |
| Exportar XLSX | Idéntica | `GET /api/reports/summary.xlsx` | Hoja única de resumen |
| Exportar PDF | Idéntica | `GET /api/reports/summary.pdf` | Tabla con estilo de marca |
| XLSX completo con gráficos | Idéntica | `GET /api/reports/full.xlsx` | 5 hojas, 2 gráficos |

### Identidad visual

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Login con fondo y cristal | Adaptada | Componente React | El cristal se **precompone** con Pillow en una imagen |
| Modo claro/oscuro | Idéntica | CSS + `prefers-color-scheme` | Persistir en `localStorage` |
| Icono de la aplicación | Idéntica | Favicon + manifest | `assets/parkium.ico` → PNG/webmanifest |
| Fuente y paleta | Idéntica | Variables CSS | Ver [06-sistema-diseno.md](06-sistema-diseno.md) |
| Sidebar con navegación | Adaptada | Sidebar colapsable | 6 entradas, condicionadas por rol |

### Mantenimiento

| Funcionalidad | Estado | Equivalente web | Notas |
|---|---|---|---|
| Respaldo de la base | **Adaptada** | Script del servidor o `pg_dump` | `backup_database` es específico de SQLite |
| Restaurar con validación | **Adaptada** | Script del servidor | `_validate_sqlite` es de SQLite |
| Diagnóstico de salud | **Adaptada** | `GET /api/health` | Sin parámetros de SQLite |
| Limpieza de sesiones | Idéntica | Tarea programada | `cleanup_expired_sessions` |
| Registro en archivo | Adaptada | Logging estructurado | `runtime/parkium.log` |

---

## 1.3 Funcionalidades dependientes de la plataforma

| Dependencia original | Web APIs / alternativa | Riesgo |
|---|---|---|
| **Spooler de Windows** (`pywin32`) | El navegador imprime vía `window.print()` con CSS `@page`. El servidor conserva ESC/POS si el equipo de la caja es Windows. | **Medio** |
| **`time.monotonic()`** | Reloj monotónico **del servidor** (Python sí lo tiene). La web nunca valida la hora: es el servidor. | **Alto** — ver [05](05-modulos-implementacion.md) §7 |
| **SQLite en archivo local** | PostgreSQL o MySQL en servidor | **Alto** — `julianday()` es específico de SQLite |
| **Archivo `runtime/`** | Almacenamiento del servidor o columnas `BYTEA` | Bajo |
| **Login local sin sesión** (`_show_recovery`) | **No exponer.** Script de consola del servidor | **Crítico** si se expone |
| **`http.server` local** (`receipt_web.py`) | Ruta real `/r/{token}` en el servidor web | Bajo |
| **Tkinter `Canvas`** | Chart.js o Recharts | Bajo |
| **Pillow** para el cristal del login | Generar la imagen en build o con el backend | Bajo |
| **PyInstaller** | Build web + CDN o assets propios | Bajo |
| **Doble clic en fila** | Clic simple o menú contextual | Bajo |
| **Atajos de teclado** de Tk | Atajos del navegador | Bajo |
| **`minsize(1080, 680)`** | Breakpoints responsive | Bajo |

---

## 1.4 Cobertura de la matriz

- **Módulos del original inventariados:** 11 de 11 (100 %).
- **Funcionalidades con equivalente web:** 100 % salvo dos marcadas
  **No portable** (recuperación local de administrador y facturación
  electrónica), ambas justificadas en [12](12-preguntas-abiertas.md).
- **Roles cubiertos:** 3 de 3.
- **Tablas cubiertas:** 25 de 25 (ver [03](03-esquema-base-datos.md)).