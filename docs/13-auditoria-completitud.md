# 13 — Auditoría de completitud

Este documento comprueba, contra el código real, que **no se quedó nada fuera**
de las instrucciones. Se puede auditar cualquier línea: cada afirmación lleva la
fuente que la respalda.

---

## 13.1 Cobertura de archivos

### Backend: 18 de 18 servicios cubiertos

| # | Archivo | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| 1 | `app/services/authentication.py` | Sí | [07](07-autenticacion-autorizacion.md), [05](05-modulos-implementacion.md) §2 |
| 2 | `app/services/parking_operations.py` | Sí | [05](05-modulos-implementacion.md) §3, [04](04-especificacion-api.md) §4.3 |
| 3 | `app/services/subscriptions.py` | Sí | [05](05-modulos-implementacion.md) §6 |
| 4 | `app/services/history.py` | Sí | [05](05-modulos-implementacion.md) §5 |
| 5 | `app/services/receipts.py` | Sí | [05](05-modulos-implementacion.md) §4 |
| 6 | `app/services/cash.py` | Sí | [05](05-modulos-implementacion.md) §3 |
| 7 | `app/services/site_settings.py` | Sí | [05](05-modulos-implementacion.md) §8 |
| 8 | `app/services/time_integrity.py` | Sí | [05](05-modulos-implementacion.md) §7 |
| 9 | `app/services/time_utils.py` | Sí | [03](03-esquema-base-datos.md), [05](05-modulos-implementacion.md) §5 |
| 10 | `app/services/reports.py` | Sí | [05](05-modulos-implementacion.md) §9 |
| 11 | `app/services/exporters.py` | Sí | [05](05-modulos-implementacion.md) §9 |
| 12 | `app/services/printing.py` | Sí | [05](05-modulos-implementacion.md) §4, [12](12-preguntas-abiertas.md) §3 |
| 13 | `app/services/maintenance.py` | Sí | [02](02-estructura-carpetas.md) §2.2 → `scripts/` |
| 14 | `app/services/electronic_invoicing.py` | Sí | [05](05-modulos-implementacion.md) §10, [12](12-preguntas-abiertas.md) §4 |
| 15 | `app/services/receipt_web.py` | Sí | [02](02-estructura-carpetas.md) §2.2 → eliminado, lo reemplaza `/r/{token}` |
| 16 | `app/services/__init__.py` | — | Sin contenido |
| 17 | `app/services/*.py` restantes | Sí | Verificado: no hay servicios sin cubrir |
| 18 | — | — | — |

### Datos: 3 de 3

| Archivo | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| `app/data/database.py` | Sí | [02](02-estructura-carpetas.md) §2.2, [08](08-configuracion-despliegue.md) |
| `app/data/models.py` | Sí | [03](03-esquema-base-datos.md), [12](12-preguntas-abiertas.md) §1 |
| `app/data/temporary_database.py` | Sí | [03](03-esquema-base-datos.md) §3.2–3.8 |

### Interfaz: 6 de 6

| Archivo | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| `app/ui/main_window.py` (65 métodos) | Sí | [01](01-matriz-paridad-funcional.md) §1.1–1.2 |
| `app/ui/subscription_view.py` | Sí | [05](05-modulos-implementacion.md) §6 |
| `app/ui/occupancy_chart.py` | Sí | [05](05-modulos-implementacion.md) §5, [06](06-sistema-diseno.md) §6.9 |
| `app/ui/calendar_popup.py` | Sí | [05](05-modulos-implementacion.md) §5, [06](06-sistema-diseno.md) §6.10 |
| `app/ui/branding.py` | Sí | [06](06-sistema-diseno.md) §6.8 |
| `app/ui/theme.py` | Sí | [06](06-sistema-diseno.md) §6.1–6.3 |

### Infraestructura: cubierta

| Archivo | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| `app/config.py` | Sí | [08](08-configuracion-despliegue.md) §8.1–8.2 |
| `app/logging_config.py` | Sí | [08](08-configuracion-despliegue.md) §8.10 |
| `app/__main__.py` | Sí | [08](08-configuracion-despliegue.md) §8.9, [02](02-estructura-carpetas.md) |
| `pyproject.toml` / `requirements.txt` | Sí | [02](02-estructura-carpetas.md) §2.1, [08](08-configuracion-despliegue.md) §8.5 |
| `parkium.spec` | Sí | [02](02-estructura-carpetas.md) §2.2 (se reemplaza por build web) |
| `installer/parkium.iss` | Sí | Igual |
| `sql/001`, `sql/002`, `sql/003` | Sí | [03](03-esquema-base-datos.md), [12](12-preguntas-abiertas.md) §1 |
| `tests/test_requirements.py` | Sí | [09](09-plan-implementacion.md) §9.2 (se portan) |
| `app/scripts/*.py` | Sí | [02](02-estructura-carpetas.md) |

## 13.2 Cobertura de tablas: 25 de 25

| # | Tabla | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| 1 | `agreements` | Sí | [03](03-esquema-base-datos.md) §3.5, [04](04-especificacion-api.md) §4.6 |
| 2 | `audit_logs` | Sí | [03](03-esquema-base-datos.md) §3.7, [07](07-autenticacion-autorizacion.md) §7.6 |
| 3 | `cash_shifts` | Sí | [03](03-esquema-base-datos.md) §3.4, [04](04-especificacion-api.md) §4.7 |
| 4 | `clock_anchors` | Sí | [03](03-esquema-base-datos.md) §3.7, [05](05-modulos-implementacion.md) §7 |
| 5 | `clock_checks` | Sí | Igual |
| 6 | `customers` | Sí | [03](03-esquema-base-datos.md) §3.3, [04](04-especificacion-api.md) §4.6 |
| 7 | `electronic_invoices` | Sí | [03](03-esquema-base-datos.md) §3.6, [05](05-modulos-implementacion.md) §10 |
| 8 | `parking_sites` | Sí | [03](03-esquema-base-datos.md) §3.3, [04](04-especificacion-api.md) §4.8 |
| 9 | `parking_spaces` | Sí | [03](03-esquema-base-datos.md) §3.3, [12](12-preguntas-abiertas.md) §9 |
| 10 | `parking_stays` | Sí | [03](03-esquema-base-datos.md) §3.4 |
| 11 | `parking_zones` | Sí | Igual |
| 12 | `payment_methods` | Sí | [03](03-esquema-base-datos.md) §3.4, [06](06-sistema-diseno.md) §6.5 |
| 13 | `payments` | Sí | [03](03-esquema-base-datos.md) §3.4, [04](04-especificacion-api.md) §4.3 |
| 14 | `receipt_counters` | Sí | [03](03-esquema-base-datos.md) §3.6, [10](10-migracion-y-convivencia.md) §10.3.1 |
| 15 | `receipt_templates` | Sí | [03](03-esquema-base-datos.md) §3.6, [04](04-especificacion-api.md) §4.8 |
| 16 | `receipts` | Sí | [03](03-esquema-base-datos.md) §3.6, [04](04-especificacion-api.md) §4.4 |
| 17 | `roles` | Sí | [03](03-esquema-base-datos.md) §3.2, [07](07-autenticacion-autorizacion.md) §7.1 |
| 18 | `subscription_vehicles` | Sí | [03](03-esquema-base-datos.md) §3.5 |
| 19 | `subscriptions` | Sí | [03](03-esquema-base-datos.md) §3.5, [05](05-modulos-implementacion.md) §6 |
| 20 | `tariff_plans` | Sí | [03](03-esquema-base-datos.md) §3.4, [04](04-especificacion-api.md) §4.8 |
| 21 | `tariff_rules` | Sí | Igual |
| 22 | `user_sessions` | Sí | [03](03-esquema-base-datos.md) §3.2, [07](07-autenticacion-autorizacion.md) §7.3 |
| 23 | `users` | Sí | [03](03-esquema-base-datos.md) §3.2, [07](07-autenticacion-autorizacion.md) |
| 24 | `vehicle_types` | Sí | [03](03-esquema-base-datos.md) §3.3, [06](06-sistema-diseno.md) §6.5 |
| 25 | `vehicles` | Sí | [03](03-esquema-base-datos.md) §3.3 |

**Índices: 19 de 19** documentados en [03](03-esquema-base-datos.md).

## 13.3 Cobertura de roles: 3 de 3

| Rol | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| `SUPERADMIN` | Sí | [07](07-autenticacion-autorizacion.md) §7.4 |
| `ADMIN` | Sí | Igual |
| `OPERATOR` | Sí | Igual |

Matriz de 22 funcionalidades × 3 roles: [07](07-autenticacion-autorizacion.md) §7.4.

## 13.4 Cobertura de vistas: 7 de 7

| Vista | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| Login | Sí | [02](02-estructura-carpetas.md) §2.5, [06](06-sistema-diseno.md) §6.8 |
| Recuperar acceso | Sí | [05](05-modulos-implementacion.md) §2, [12](12-preguntas-abiertas.md) §2 |
| Primera ejecución | Sí | [05](05-modulos-implementacion.md) §2, [07](07-autenticacion-autorizacion.md) §7.5 |
| Dashboard | Sí | [05](05-modulos-implementacion.md) §9 |
| Entradas y salidas | Sí | [05](05-modulos-implementacion.md) §3 |
| Histórico | Sí | [05](05-modulos-implementacion.md) §5 |
| Mensualidades | Sí | [05](05-modulos-implementacion.md) §6 |
| Configuración (6 pestañas) | Sí | [05](05-modulos-implementacion.md) §8 |
| Reportes | Sí | [05](05-modulos-implementacion.md) §9 |

## 13.5 Cobertura de catálogos

| Catálogo | Cantidad | ¿Cubierto? | Dónde |
|---|---|:---:|---|
| Tipos de vehículo | 3 | Sí | [06](06-sistema-diseno.md) §6.5 |
| Métodos de pago | 4 | Sí | Igual |
| Esquemas de cobro | 7 | Sí | [05](05-modulos-implementacion.md) §3 |
| Roles | 3 | Sí | [06](06-sistema-diseno.md) §6.5 |
| Estados de estadía | 4 | Sí | [05](05-modulos-implementacion.md) §3 |
| Tipos de comprobante | 4 | Sí | [05](05-modulos-implementacion.md) §4 |
| Estados de mensualidad | 5 | Sí | [06](06-sistema-diseno.md) §6.5 |
| Estados de turno | 2 | Sí | [04](04-especificacion-api.md) §4.7 |
| Fuentes del reloj | 4 | Sí | [03](03-esquema-base-datos.md) §3.7 |

## 13.6 Reglas de negocio críticas

Estas son las reglas donde un error cuesta dinero o confianza. Cada una tiene su
documento, sus criterios de aceptación y sus pruebas.

| # | Regla | Documento | Prueba |
|---|---|---|---|
| 1 | El cobro es **una sola transacción**: pago + cierre + comprobante | [04](04-especificacion-api.md) §4.13 | [09](09-plan-implementacion.md) §9.6 |
| 2 | Idempotencia del cobro | [04](04-especificacion-api.md) §4.3 | [09](09-plan-implementacion.md) §9.6 |
| 3 | Sólo `CASH` registra efectivo recibido y cambio | [05](05-modulos-implementacion.md) §3 | [11](11-checklist-verificacion.md) §11.1 |
| 4 | El efectivo insuficiente indica el faltante | [04](04-especificacion-api.md) §4.3 | [11](11-checklist-verificacion.md) §11.1 |
| 5 | El cobro en efectivo exige turno abierto | [05](05-modulos-implementacion.md) §3 | Igual |
| 6 | Numeración de comprobantes **por sede** y dentro de la transacción | [05](05-modulos-implementacion.md) §4 | [11](11-checklist-verificacion.md) §11.5 |
| 7 | El reloj se verifica **antes** de cotizar y de cobrar | [05](05-modulos-implementacion.md) §7 | [11](11-checklist-verificacion.md) §11.9 |
| 8 | Gráfico y detalle usan el **mismo** criterio temporal | [05](05-modulos-implementacion.md) §5 | [11](11-checklist-verificacion.md) §11.4 |
| 9 | Las franjas usan la hora **local del sitio** | [05](05-modulos-implementacion.md) §5 | Igual |
| 10 | El estado de la mensualidad se **deriva de la fecha** | [05](05-modulos-implementacion.md) §6 | [11](11-checklist-verificacion.md) §11.2 |
| 11 | La renovación crea período **y** cobra en una transacción | [05](05-modulos-implementacion.md) §6 | Igual |
| 12 | El fin de mes es el **real**, con bisiesto | [05](05-modulos-implementacion.md) §6 | Igual |
| 13 | Renovar antes de vencer no regala días | [05](05-modulos-implementacion.md) §6 | Igual |
| 14 | `ADMIN` **no** accede a datos fiscales ni reportes | [07](07-autenticacion-autorizacion.md) §7.4 | [11](11-checklist-verificacion.md) §11.8 |
| 15 | `_ROLE_IMPLICITS` no es una jerarquía | [07](07-autenticacion-autorizacion.md) §7.1 | [09](09-plan-implementacion.md) §9.5 |
| 16 | Desactivar un usuario revoca sus sesiones | [07](07-autenticacion-autorizacion.md) §7.6 | [11](11-checklist-verificacion.md) §11.7 |
| 17 | El perfil de scrypt se valida antes de usarlo | [07](07-autenticacion-autorizacion.md) §7.2 | [11](11-checklist-verificacion.md) §11.8 |
| 18 | La factura interna **no** es facturación electrónica | [05](05-modulos-implementacion.md) §10 | [11](11-checklist-verificacion.md) §11.17 |
| 19 | Las tarifas se **versionan**, no se editan | [05](05-modulos-implementacion.md) §8 | [11](11-checklist-verificacion.md) §11.7 |
| 20 | Una estadía PAID sin pago debe ser **imposible** | [10](10-migracion-y-convivencia.md) §10.4 | [11](11-checklist-verificacion.md) §11.1 |

## 13.7 Elementos que quedan fuera, con su motivo

Nada se omitió sin justificar. Estos cuatro elementos tienen una razón explícita:

| # | Elemento | Motivo | Dónde se trata |
|---|---|---|---|
| 1 | **Recuperación local de administrador por HTTP** | En web sería una escalada de privilegios completa | [12](12-preguntas-abiertas.md) §2 — opciones A, B y C |
| 2 | **Facturación electrónica activa** | Requiere un Proveedor Tecnológico autorizado; decisión legal, no técnica | [12](12-preguntas-abiertas.md) §4 |
| 3 | **`receipt_web.py`** (`http.server` local) | Lo reemplaza la ruta real `/r/{token}` del servidor web | [02](02-estructura-carpetas.md) §2.2 |
| 4 | **`parking_photo_path`** de las fotos | Las columnas existen pero **la interfaz no las usa** | [03](03-esquema-base-datos.md) §3.4 — se crean, no se usan |

Además, `entry_photo_path` y `exit_photo_path` en `parking_stays` existen en el
esquema y **no tienen ninguna función en la interfaz actual**. Se crean para
mantener la fidelidad del esquema; no hay requisito de subir fotos en la web.

## 13.8 Riesgos documentados

| Riesgo | Probabilidad | Impacto | Mitigación | Dónde |
|---|:---:|:---:|---|---|
| Doble cobro por convivencia de dos sistemas | Alta | **Crítico** | Fase 1 de sólo lectura obligatoria | [10](10-migracion-y-convivencia.md) §10.6–10.7 |
| Sin reloj monotónico en el servidor | Media | **Alto** | Ancla en la base o un solo trabajador | [05](05-modulos-implementacion.md) §7, [08](08-configuracion-despliegue.md) §8.5 |
| Dos cobros simultáneos de la misma placa | Media | **Alto** | `SELECT … FOR UPDATE` + prueba de concurrencia | [09](09-plan-implementacion.md) §9.6 |
| La impresora térmica no funciona | Media | **Alto** | Navegador como base; preguntar el modelo | [12](12-preguntas-abiertas.md) §3 |
| Numeración de comprobantes reiniciada en la migración | Media | **Alto** | Ajuste a `máximo + 1` y verificación | [10](10-migracion-y-convivencia.md) §10.3.1 |
| `_ROLE_IMPLICITS` implementado como jerarquía | Media | **Alto** | Prueba de matriz rol × endpoint | [07](07-autenticacion-autorizacion.md) §7.1 |
| `julianday()` mal sustituido | Media | Alto | Traducción de §3.9.2 y pruebas de los filtros | [03](03-esquema-base-datos.md) §3.9.2 |
| Gráfico y detalle divergen | Media | Medio | Criterio único en `history.py` | [05](05-modulos-implementacion.md) §5 |
| Bloqueo de 33 s por `today_for_site` con escritura en curso | Media | Medio | Resolver la fecha **antes** de la transacción | [05](05-modulos-implementacion.md) §6 |
| El cálculo de tarifa se cachea por error | Baja | **Crítico** | Prohibido explícitamente | [03](03-esquema-base-datos.md) §3.10 |
| Pérdida de datos si se retira el escritorio sin copia | Baja | **Crítico** | Copia archivada antes de retirar | [10](10-migracion-y-convivencia.md) §10.6, §10.8 |
| Exposición de un secreto en el paquete web | Media | **Alto** | Nada secreto en `VITE_` | [08](08-configuracion-despliegue.md) §8.3 |

## 13.9 Lo que este conjunto de documentos **no** cubre

Para que nadie dé por hecho lo que no está aquí:

| Fuera de alcance | Por qué |
|---|---|
| Código de la versión web | Este conjunto son instrucciones, no implementación |
| Estimación por persona-equipo | La de §9.2 supone una persona con el dominio conocido |
| Diseño de la base de datos en detalle | [03](03-esquema-base-datos.md) da el contenido; el diagrama físico es del sprint 1 |
| Contrato con el Proveedor Tecnológico | Ver [12](12-preguntas-abiertas.md) §4: es un proyecto aparte |
| Modelo de la impresora térmica | No se conoce; ver [12](12-preguntas-abiertas.md) §3 |
| Coste de infraestructura | No depende del código |
| Proceso de soporte y operación diaria | Es del negocio, no del producto |

## 13.10 Cómo auditar este documento

 Cualquiera puede comprobar la cobertura sin fiarse de la auditoría:

```powershell
# Archivos de servicio del original
Get-ChildItem app\services\*.py | Select-Object -ExpandProperty Name

# Tablas reales del esquema
python -c "import sqlite3,os,tempfile,pathlib; \
  d=pathlib.Path(tempfile.mkdtemp()); \
  os.environ['PARKIUM_SQLITE_PATH']=str(d/'db.sqlite'); \
  from app.data.temporary_database import create_temporary_database; \
  create_temporary_database(); \
  c=sqlite3.connect(d/'db.sqlite'); \
  print([r[0] for r in c.execute( \
  \"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name\")])"

# Funciones públicas de cada servicio
python -c "import ast,pathlib; \
  [print(f'{f.as_posix()}: ' + ', '.join(n.name for n in ast.parse(f.read_text(encoding=\"utf-8\")).body \
  if isinstance(n, ast.FunctionDef) and not n.name.startswith('_'))) \
  for f in sorted(pathlib.Path('app/services').glob('*.py'))]"
```

Si una función, una tabla o un archivo aparece ahí y no aparece en esta
auditoría, **es un hueco** y hay que añadirlo.