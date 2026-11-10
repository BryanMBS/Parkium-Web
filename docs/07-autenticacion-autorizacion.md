# 07 — Autenticación, autorización y sesión

## 7.1 Modelo de identidad

El original define **tres roles** en `app/services/authentication.py`:

```python
ROLE_SUPERADMIN = "SUPERADMIN"
ROLE_ADMIN     = "ADMIN"
ROLE_OPERATOR  = "OPERATOR"
ROLES = (ROLE_SUPERADMIN, ROLE_ADMIN, ROLE_OPERATOR)

_ROLE_IMPLICITS = {
    ROLE_SUPERADMIN: frozenset(ROLES),          # satisface cualquier requisito
    ROLE_ADMIN:     frozenset({ROLE_ADMIN}),
    ROLE_OPERATOR:  frozenset({ROLE_OPERATOR}),
}
```

Etiquetas legibles (`ROLE_LABELS`):

| Código | Etiqueta en la interfaz |
|---|---|
| `SUPERADMIN` | Super administrador |
| `ADMIN` | Administrador |
| `OPERATOR` | Operador |

> **Punto que suele malinterpretarse:** `_ROLE_IMPLICITS` **no** crea una
> jerarquía del tipo «admin ≥ operador». `ADMIN` sólo satisface requisitos que
> aceptan `ADMIN`; si una función exige `SUPERADMIN` o `OPERATOR`, un `ADMIN`
> pasa igual. Implementar «admin puede hacer todo lo del operador» cambiaría el
> modelo de autorización y abriría permisos que hoy no existen.

### Descripciones de rol (semilla de datos)

| Código | Descripción en la base |
|---|---|
| `ADMIN` | Configuración operativa, usuarios y caja. Sin reportes ni datos fiscales. |
| `OPERATOR` | Registra entradas, salidas, cobros y su caja. |
| `SUPERADMIN` | Acceso total: datos del parqueadero, plantillas, reportes y usuarios. |

## 7.2 Contraseñas

| Parámetro | Valor | Símbolo |
|---|---|---|
| Algoritmo | **scrypt** | `hashlib.scrypt` |
| Coste N | 16 384 | `SCRYPT_N` |
| Bloque r | 8 | `SCRYPT_R` |
| Paralelismo p | 1 | `SCRYPT_P` |
| Longitud mínima | 10 | `PASSWORD_MIN_LENGTH` |
| Longitud máxima | 256 | `PASSWORD_MAX_LENGTH` |
| Formato de usuario | `^[A-Za-z0-9._-]{3,60}$` | `_USERNAME_PATTERN` |

El hash se guarda **autodescriptivo**: los parámetros persisten en la propia
cadena para que un cambio de perfil no invalide los hashes existentes.

> **Control importante ya implementado:** sólo se acepta el perfil seguro
> vigente (`N=16384, r=8, p=1`). Si una fila de la base hubiera sido manipulada
> para pedir una reserva de memoria enorme durante el inicio de sesión, el
> código la rechaza. **La web debe replicar esta validación**, no leer el
> perfil desde la base y usarlo sin comprobarlo.

Formato almacenado en `users.password_hash`:

```
scrypt$N$r$p$<salida base64url>$<hash base64url>
```

## 7.3 Sesiones

| Aspecto | Valor | Fuente |
|---|---|---|
| Duración | **12 horas** | `SESSION_DURATION` |
| Token | aleatorio, opaco, de un solo uso por sesión | `authenticate` |
| Almacenamiento | **SHA-256 del token** | `_token_hash` |
| Tabla | `user_sessions` | — |
| Revocación | `revoked_at` | `logout` |
| Limpieza | `cleanup_expired_sessions` en el arranque | `app/__main__.py` |

> El token **nunca** se guarda en claro: sólo su hash SHA-256. Aunque alguien
> lea la tabla completa, no puede suplantar una sesión.

### Implementación en la web

```python
# backend/app/api/auth.py
@router.post("/login", response_model=LoginResponse)
def login(cuerpo: LoginRequest, respuesta: Response, db: Session = Depends(get_db)):
    usuario = authenticate(cuerpo.usuario, cuerpo.contrasena, db)
    token = secrets.token_urlsafe(32)
    expiracion = datetime.now(UTC) + SESSION_DURATION
    db.add(SessionRow(
        user_id=usuario.id,
        token_hash=sha256_hex(token),
        expires_at=expiracion,
    ))
    db.commit()
    respuesta.set_cookie(
        "parkium_sesion", token,
        httponly=True,     # invisible para JavaScript
        secure=True,       # sólo HTTPS
        samesite="lax",    # no se envía en enlaces de terceros
        max_age=int(SESSION_DURATION.total_seconds()),
        path="/",
    )
    return LoginResponse(usuario=..., expira_en=expiracion)
```

```python
# backend/app/deps.py
def get_current_user(request: Request, db: Session = Depends(get_db)) -> AuthenticatedUser:
    token = request.cookies.get("parkium_sesion")
    if not token:
        raise HTTPException(401, detail=ErrorBody(codigo="no_autenticado"))
    registro = db.query(SessionRow).filter(
        SessionRow.token_hash == sha256_hex(token),
    ).first()
    if registro is None or registro.revoked_at or registro.expires_at <= datetime.now(UTC):
        raise HTTPException(401, detail=ErrorBody(codigo="no_autenticado"))
    usuario = db.query(UserRow).filter(UserRow.id == registro.user_id).first()
    if usuario is None or not usuario.is_active:
        raise HTTPException(401, detail=ErrorBody(codigo="no_autenticado"))
    return AuthenticatedUser(id=usuario.id, ...)
```

| Regla de cookie | Valor | Motivo |
|---|---|---|
| `HttpOnly` | obligatorio | El token no debe ser legible desde JavaScript: una XSS no debe robar la sesión |
| `Secure` | obligatorio en producción | El token no viaja en claro |
| `SameSite=Lax` | recomendado | Evita el envío en peticiones POST de terceros |
| Sin `localStorage` | prohibido | Es accesible desde JavaScript; es exactamente lo que `HttpOnly` evita |

## 7.4 Matriz de autorización

Cada celda indica el endpoint, el rol mínimo y su origen en el original.

| Funcionalidad | `OPERATOR` | `ADMIN` | `SUPERADMIN` | Origen |
|---|:---:|:---:|:---:|---|
| Ver dashboard del día | Sí | Sí | Sí | `dashboard_summary` |
| Registrar entrada | Sí | Sí | Sí | `register_entry` |
| Cotizar salida | Sí | Sí | Sí | `quote_exit` |
| **Cobrar salida** | Sí | Sí | Sí | `collect_payment` |
| Emitir comprobante | Sí | Sí | Sí | `issue_receipt` |
| Reimprimir comprobante | Sí | Sí | Sí | `reprint_receipt_for_user` |
| Consultar su turno de caja | Sí | Sí | Sí | `cash.list_open_shifts` |
| **Abrir y cerrar su caja** | Sí | Sí | Sí | `open_cash_shift`, `close_cash_shift` |
| Ver turno de otro usuario | No | Sí | Sí | `require_admin` |
| **Mensualidades (todo el módulo)** | **No** | **Sí** | **Sí** | Pestaña condicionada en `_show_subscriptions` |
| **Histórico** | **No** | **Sí** | **Sí** | Pestaña condicionada en `_show_history` |
| Ver tarifas | No | Sí | Sí | `configure_tariff` |
| Crear tarifas | No | Sí | Sí | `configure_tariff` |
| Crear usuario **operador** | No | Sí | Sí | `create_user` |
| Crear usuario **admin** | No | Sí | Sí | `create_user` |
| **Crear usuario super admin** | No | **No** | **Sí** | `require_superadmin` en `create_user` |
| Cambiar contraseña de normal | No | Sí | Sí | `change_user_password` |
| **Cambiar contraseña de super admin** | No | **No** | **Sí** | Misma regla |
| Activar/desactivar usuario | No | Sí | Sí | `set_user_active` |
| **Datos fiscales (NIT, nombre, dirección)** | No | **No** | **Sí** | `require_superadmin` |
| **Editar plantilla de factura** | No | **No** | **Sí** | `require_superadmin` |
| **Reportes consolidados** | No | **No** | **Sí** | `_require_report_access` |
| **Exportar XLSX completo** | No | **No** | **Sí** | `require_superadmin` |
| **Cambiar contraseña propia** | Sí | Sí | Sí | `change_own_password` |

> **`ADMIN` es una categoría propia, no superior a `OPERATOR`.** El operador
> puede cobrar (y por tanto manipula dinero en su turno) pero no ve reportes ni
> mensualidades; el administrador ve mensualidades e histórico pero no los datos
> fiscales. Es una separación deliberada de responsabilidades.

## 7.5 Recuperación local de administrador

`reset_administrator_password` restablece la contraseña de una cuenta
**administrativa** (`ADMIN` o `SUPERADMIN`) sin exigir la anterior, reactiva la
cuenta y revoca sus sesiones. El símbolo de auditoría es `PASSWORD_RESET_LOCAL`.
Hoy eso es aceptable porque el asistente se abre en la propia máquina del
operador.

En una web eso sería una escalada de privilegios completa: cualquiera con acceso
a `/recuperar` podría tomar el control.

| Opción | Descripción | Valoración |
|---|---|---|
| **A — No exponer** | Script de consola del servidor | **Recomendada** |
| B — Correo al super admin | Un correo con enlace de un solo uso | Necesita correo saliente, que el original **no tiene** |
| C — Clave de rescate | Frase maestra en variable de entorno + código de un solo uso | Viable; hay que definir la rotación |

**Recomendación: opción A**, complementada con un procedimiento documentado de
rescate. Ver [12-preguntas-abiertas.md](12-preguntas-abiertas.md) §2.

### Contraseña del primer super administrador

El original muestra un asistente de primera ejecución
(`_show_first_run` → `_complete_first_run`), que crea un `SUPERADMIN`
(`create_first_administrator`, símbolo `USER_CREATED_INITIAL_SUPERADMIN`). En
web, lo equivalente es un script de despliegue:

```bash
python scripts/create_first_admin.py --usuario bsmb --nombre "Root" --rol SUPERADMIN
```

El endpoint `POST /api/auth/first-user` queda **cerrado por defecto** y sólo se
abre si `has_users()` es falso, para no dejar una puerta abierta por descuido.

## 7.6 Auditoría de accesos y acciones sensibles

`audit_logs` registra lo que el original considera relevante. La web debe
mantener la misma cobertura y **llenar `ip_address`**, que hoy está disponible
pero sin usar.

| Acción | Registrada | Símbolo exacto en el código |
|---|:---:|---|
| Inicio de sesión correcto | Sí | `LOGIN_SUCCESS` |
| Inicio de sesión fallido | Sí | `LOGIN_FAILED` (con `user_id` nulo, `entity_type='AUTH'`) |
| Cierre de sesión | Sí | `LOGOUT` |
| Alta del primer super admin | Sí | `USER_CREATED_INITIAL_SUPERADMIN` |
| Alta de usuario | Sí | `USER_CREATED` (con el rol en `after_data`) |
| Cambio de activación | Sí | `USER_ACTIVATION_CHANGED` |
| Cambio de contraseña propia | Sí | `PASSWORD_CHANGED` |
| Cambio de contraseña por un admin | Sí | `PASSWORD_RESET_BY_ADMIN` |
| Recuperación local de admin | Sí | `PASSWORD_RESET_LOCAL` |
| Promoción a super admin | Sí | `USER_PROMOTED_TO_SUPERADMIN` |
| Cliente creado | Sí | `CUSTOMER_CREATED` |
| Placa asociada | Sí | `VEHICLE_ATTACHED` |
| Cobro de mensualidad | Sí | `SUBSCRIPTION_PAYMENT` |
| Renovación | Sí | `SUBSCRIPTION_RENEWED` |
| Cancelación | Sí | `SUBSCRIPTION_CANCELLED` |
| Alta, baja y edición de usuarios | Sí | Ver arriba |
| Cambio de datos del parqueadero | Sí | Incluye NIT |
| Cambio de plantilla de factura | Sí | — |
| Creación de tarifa | Sí | — |
| Apertura y cierre de turno | Sí | Con los tres importes |
| Cobro de salida | Sí | Con importe, método y cambio |
| Anulación de cobro | Sí | Con motivo |
| Reimpresión de comprobante | Sí | Con el contador |
| Verificación del reloj | Sí | Con deriva y fuente |

### Reglas de revocación ya implementadas en el original

Verificadas literalmente en `app/services/authentication.py`:

| Acción | Efecto sobre las sesiones |
|---|---|
| `set_user_active(..., False)` | Revoca **todas** las sesiones abiertas del usuario |
| `change_own_password(...)` | Revoca todas las sesiones **salvo la actual** (`token_hash <> ?`) |
| `change_user_password(...)` | Revoca **todas** las sesiones del usuario objetivo |
| `reset_administrator_password(...)` | Revoca todas las sesiones, reactiva la cuenta (`is_active = 1`) |
| `logout(...)` | Revoca sólo la sesión actual |

Y dos bloqueos que la web debe conservar:

| Bloqueo | Mensaje en el original |
|---|---|
| Desactivar la propia cuenta | «No puede desactivar su propia cuenta.» |
| Un `ADMIN` que toque la cuenta de un `SUPERADMIN` | «No puede modificar la cuenta de un super administrador.» / «No puede cambiar la contraseña de un super administrador.» |

### Estructura de una entrada

```json
{
  "user_id": 1,
  "entity_type": "subscription",
  "entity_id": 7,
  "action": "SUBSCRIPTION_RENEWED",
  "before_data": { "expires_on": "2026-10-30", "status": "ACTIVE" },
  "after_data":  { "expires_on": "2026-11-29", "status": "ACTIVE" },
  "occurred_at": "2026-10-08T14:32:10+00:00",
  "ip_address": "190.85.60.20"
}
```

Reglas: **`before_data` y `after_data` nunca incluyen contraseñas ni tokens**;
`user_id` puede ser nulo para operaciones sin sesión (mantenimiento, semillas);
la auditoría **no se puede borrar desde la interfaz**.

## 7.7 Endurecimiento de la sesión

| Medida | Detalle |
|---|---|
| Limitar intentos de login | 5 por usuario cada 15 min, con bloqueo creciente |
| Invalidar al desactivar | Ya implementado: `set_user_active(False)` revoca las sesiones abiertas |
| Invalidar al cambiar contraseña | Ya implementado: la propia conserva la actual; la de otro, todas |
| Rotar el token al iniciar sesión | `secrets.token_urlsafe(32)` en cada `authenticate` |
| `Cache-Control: no-store` | En login y en toda respuesta con datos del usuario |
| Cabeceras | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer` |
| CSP | `default-src 'self'`; sin `unsafe-inline` en producción |

## 7.8 Lista de verificación de seguridad

- [ ] El hash de una contraseña nunca sale de la base ni de una respuesta.
- [ ] El token de sesión nunca aparece en `localStorage`, en una URL ni en un registro.
- [ ] La cookie tiene `HttpOnly`, `Secure` y `SameSite`.
- [ ] `require_role` se replica literalmente, sin jerarquías implícitas.
- [ ] Un `ADMIN` recibe `403` en datos fiscales, plantillas y reportes.
- [ ] Un `OPERATOR` recibe `403` en mensualidades, histórico y configuración.
- [ ] Desactivar un usuario invalida sus sesiones en el acto.
- [ ] El perfil de scrypt se valida contra la lista segura antes de usarlo.
- [ ] `audit_logs.ip_address` se llena.
- [ ] La recuperación de administrador no está expuesta por HTTP.
- [ ] `POST /api/auth/first-user` responde `409` si ya hay usuarios.
- [ ] Los intentos de login fallidos quedan auditados.