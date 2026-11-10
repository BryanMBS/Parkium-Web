# 08 — Configuración, entornos y despliegue

## 8.1 Configuración del original

`app/config.py` resuelve su configuración desde el entorno y expone un objeto
único. `.env.example` documenta las variables.

| Variable | Propósito |
|---|---|
| `PARKIUM_SQLITE_PATH` | Ruta del archivo de base en desarrollo |
| `PARKIUM_MYSQL_*` | Servidor, base, usuario y contraseña de MySQL en producción |
| `PARKIUM_DATA_DIR` | Carpeta de datos (`runtime/`) |
| `PARKIUM_TIME_SOURCE_URL` | Fuente externa para verificar la hora |
| `PARKIUM_EINVOICE_PROVIDER` | Proveedor de facturación electrónica; `DISABLED` por defecto |
| `PARKIUM_RECEIPT_PORT` | Puerto del servidor local de QR |

En la web hay que separar tres cosas que el original mezcla en un solo proceso:
la configuración **del servidor**, la del **frontend** (expuesta al navegador) y
los **secretos**.

## 8.2 Variables de la API

Con `pydantic-settings`:

```python
# backend/app/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PARKIUM_", env_file=".env")

    entorno: Literal["desarrollo", "pruebas", "produccion"] = "desarrollo"

    # Base de datos
    url_base: str                       # postgresql://parkium:***@db:5432/parkium
    # La contraseña viene de una variable aparte leída de un secreto, para que
    # la URL con usuario y base se pueda mostrar en registros sin filtrarla.
    password_base: SecretStr

    # Seguridad
    duracion_sesion_horas: int = 12     #=SESSION_DURATION
    longitud_minima_contrasena: int = 10
    origenes_permitidos: list[str] = ["http://localhost:5173"]

    # Reloj
    url_fuente_hora: str = "https://www.google.com/generate_204"
    espera_maxima_fuente_hora: float = 6.0

    # Comprobantes
    url_publica_base: str               # https://parkium.ejemplo.com

    # Facturación electrónica: NO ACTIVAR sin Proveedor Tecnológico autorizado
    proveedor_facturacion: str = "DISABLED"

    # Impresión ESC/POS: sólo si el servidor es Windows
    impresora_termica: str | None = None

settings = Settings()
```

### Tabla de variables

| Variable | Tipo | Por defecto | Sensible |
|---|---|---|:---:|
| `PARKIUM_ENTORNO` | texto | `desarrollo` | No |
| `PARKIUM_URL_BASE` | texto | — | **Sí** |
| `PARKIUM_ORIGENES_PERMITIDOS` | lista | `http://localhost:5173` | No |
| `PARKIUM_DURACION_SESION_HORAS` | entero | `12` | No |
| `PARKIUM_LONGITUD_MINIMA_CONTRASENA` | entero | `10` | No |
| `PARKIUM_URL_FUENTE_HORA` | URL | `google.com/generate_204` | No |
| `PARKIUM_ESPERA_MAXIMA_FUENTE_HORA` | flotante | `6.0` | No |
| `PARKIUM_URL_PUBLICA_BASE` | URL | — | No |
| `PARKIUM_PROVEEDOR_FACTURACION` | texto | `DISABLED` | No |
| `PARKIUM_IMPRESORA_TERMICA` | texto | `null` | No |
| `PARKIUM_PASSWORD_BASE` | texto | leída del secreto | **Sí** |

> **No inventes una variable para la clave de la API.** En la web **no hay**
> autenticación por clave para las peticiones del navegador: la sesión en cookie
> es el mecanismo. La clave sólo se usa en la conexión a la base y para firmar
> enlaces de un solo uso.

## 8.3 Configuración del frontend

Sólo tres valores, y ninguno es secreto:

```ts
// frontend/.env.production
VITE_API_URL=https://api.parkium.ejemplo.com
VITE_VERSION=1.0.0
VITE_TIEMPO_SESION_MINUTOS=720
```

> **Regla dura:** nada que empiece por `VITE_` puede ser un secreto. Vite
> incrusta esas variables **en el paquete que descarga el navegador**. Cualquiera
> que abra las herramientas de desarrollo las ve.

## 8.4 Estructura de la configuración

```
deploy/
├── .env.example                  # Plantilla, sin valores reales
├── .env.production                # Secretos reales. NO en el repositorio.
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.web
└── nginx.conf
```

`backend/.gitignore` debe excluir `.env` y `backend/app/state/` (anclas del
reloj, caché de plantillas).

## 8.5 Imágenes de contenedor

### `Dockerfile.api`

```dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Necesario para Pillow y psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
      "SQLAlchemy>=2.0,<3.0" "psycopg[binary]>=3.2" \
      "fastapi>=0.115" "uvicorn[standard]>=0.32" \
      "pydantic-settings>=2.6" "alembic>=1.14" \
      "reportlab>=4.0,<5.0" "Pillow>=11.0" "qrcode[pil]>=7.4" \
      "python-barcode>=0.15" "openpyxl>=3.1" "tzdata>=2024.1"

COPY backend/ ./
RUN useradd --system --uid 10001 parkium \
    && chown -R parkium:parkium /srv
USER parkium

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

> **Sobre los trabajadores:** el módulo de reloj guarda un ancla por proceso
> (`boot_id`). Con varios trabajadores habría varias anclas. **Opciones:**
> un solo trabajador con Gunicorn y hilos (`--workers 1 --threads 8`), que es lo
> recomendado para una app de mostrador; o mover el ancla a la base y usar un
> bloqueo consultivo. La primera es más simple y suficiente para la carga real.

### `Dockerfile.web`

```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
```

## 8.6 `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: parkium
      POSTGRES_USER: parkium
      POSTGRES_PASSWORD_FILE: /run/secrets/pg_password
    secrets: [pg_password]
    volumes: [pgdata:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U parkium -d parkium"]
      interval: 10s
      retries: 5
    restart: unless-stopped

  api:
    build: { context: ., dockerfile: deploy/Dockerfile.api }
    env_file: [deploy/.env.production]
    environment:
      # La URL completa, incluida la contraseña, llega por variable de entorno.
      # La contraseña va en el secreto de Docker, no en este YAML versionado.
      PARKIUM_URL_BASE: ${PARKIUM_URL_BASE}
    depends_on:
      db: { condition: service_healthy }
    restart: unless-stopped

  web:
    build: { context: ., dockerfile: deploy/Dockerfile.web }
    ports: ["80:80"]
    depends_on: [api]
    restart: unless-stopped

volumes:
  pgdata:
secrets:
  pg_password:
    file: ./deploy/.pg_password
```

> **La contraseña de la base** va en el secreto de Docker
> (`deploy/.pg_password`), nunca en este YAML versionado. `pg_password` está
> declarado como secreto precisamente para eso.

## 8.7 `nginx.conf`

```nginx
server {
    listen 80;
    server_name parkium.ejemplo.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name parkium.ejemplo.com;

    ssl_certificate     /etc/letsencrypt/live/parkium.ejemplo.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/parkium.ejemplo.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header Referrer-Policy no-referrer always;

    # La SPA: siempre index.html, para que /historico funcione al recargar
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    location /assets/ {
        root /usr/share/nginx/html;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;      # para audit_logs.ip_address
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }

    # Recibo público: sin cabecera de sesión, caché desactivado
    location /r/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        add_header Cache-Control "no-store" always;
    }

    client_max_body_size 2m;
}
```

> `X-Real-IP` es lo que permite llenar `audit_logs.ip_address`, que en el
> original está disponible pero sin usar. Sin esta cabecera, el campo seguirá
> vacío.

## 8.8 Despliegue

### Desarrollo

```bash
# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
alembic upgrade head
python scripts/create_first_admin.py --usuario bsmb --nombre "Root"
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm ci
npm run dev      # http://localhost:5173
```

### Producción

```bash
# 1. Configurar
cp deploy/.env.example deploy/.env.production
#    Rellenar: URL de la base, origenes permitidos, URL pública

# 2. Levantar
docker compose up -d --build

# 3. Crear el primer super administrador (dentro del contenedor)
docker compose exec api python scripts/create_first_admin.py --usuario bsmb --nombre "Root"

# 4. Verificar
curl https://parkium.ejemplo.com/api/health
```

### Migraciones

```bash
docker compose exec api alembic upgrade head        # aplicar
docker compose exec api alembic current             # estado
docker compose exec api alembic downgrade -1        # revertir uno
```

> **Nunca** se ejecuta `create_all` en producción: no es reversible y no registra
> el historial de cambios del esquema.

## 8.9 Copias de seguridad

El original resuelve esto con `backup_database` y `restore_database` sobre
SQLite, con una validación previa (`_validate_sqlite`) que rechaza un archivo
ajeno. En PostgreSQL la validación es la de `pg_restore`.

### Script de respaldo

```bash
#!/usr/bin/env bash
set -euo pipefail
DESTINO="${1:-/respaldos/parkium}"
FECHA=$(date +%Y%m%d_%H%M%S)
mkdir -p "$DESTINO"
pg_dump --format=custom --file="$DESTINO/parkium_$FECHA.dump" "$PARKIUM_URL_BASE"
pg_restore --list "$DESTINO/parkium_$FECHA.dump" > /dev/null   # validar
find "$DESTINO" -name 'parkium_*.dump' -mtime +30 -delete
```

### Política recomendada

| Aspecto | Valor |
|---|---|
| Frecuencia | Diaria, automática |
| Retención | 30 días diarios + 12 mensuales |
| Cifrado | Obligatorio en reposo si el respaldo sale del servidor |
| Copia fuera del servidor | Al menos una, en otra ubicación |
| **Prueba de restauración** | **Mensual, de verdad** — un respaldo sin restaurar no es un respaldo |
| Tiempo de recuperación objetivo | < 1 hora |

> **El original ya crea un respaldo diario automático** en el arranque
> (`app/__main__.py`). La web debe hacerlo con una tarea programada del sistema
> (`cron`, `systemd timer` o un contenedor), no con un proceso que arranca con la
> aplicación: si el servidor no se reincia, no hay respaldo.

## 8.10 Observabilidad

| Pieza | Implementación | Nota |
|---|---|---|
| Registro | `logging` con JSON a stdout | El original escribe `runtime/parkium.log`; en web, la salida la recoge el orquestador |
| Trazas | identificador de petición en cada línea | Permite seguir una petición completa |
| Métricas | `/api/health` + contadores Prometheus | Cobros por minuto, latencia de cotización, tasa de error |
| Alerta crítica | **`verify_clock` marca el reloj como sospechoso** | Un cobro bloqueado por reloj es una caída del negocio |
| Trazas de base | `alembic` + `pg_stat_statements` | Detectar consultas lentas al crecer el histórico |
| Centralizado | Loki, CloudWatch, Datadog o equivalente | La web es el sistema crítico; el escritorio no lo era |

## 8.11 Copia de la configuración original

Estos valores del original se conservan **idénticos** en la web porque
representan reglas de negocio, no decisiones técnicas:

| Valor | Regla |
|---|---|
| 12 h de sesión | Política de acceso |
| scrypt N=16384, r=8, p=1 | Política de contraseñas |
| Mínimo 10 caracteres | Política de contraseñas |
| `America/Bogota` como zona del sitio | Define el día local y el cálculo de ocupación |
| Capacidad 30 cupos (semilla) | Configuración inicial, editable |
| Nombres de días y meses en español | Requisito de la interfaz |

Y estos **cambian** porque son decisiones de plataforma:

| Original | Web |
|---|---|
| `runtime/tema.json` | `localStorage` |
| Archivo SQLite | PostgreSQL |
| `runtime/*.png` de comprobantes | Descarga HTTP o almacenamiento de objetos |
| Spooler de Windows | Navegador, y ESC/POS opcional en el servidor |
| Respaldo desde Python | `pg_dump` |

## 8.12 Lista de verificación de despliegue

- [ ] `deploy/.env.production` está en `.gitignore` y no está versionado.
- [ ] Ninguna variable `VITE_` contiene un secreto.
- [ ] HTTPS activo; la cookie de sesión con `Secure`.
- [ ] `PARKIUM_URL_PUBLICA_BASE` coincide con el dominio real (los QR del papel lo necesitan).
- [ ] `PARKIUM_ORIGENES_PERMITIDOS` no incluye `*`.
- [ ] `PARKIUM_PROVEEDOR_FACTURACION=DISABLED`.
- [ ] `alembic upgrade head` aplicado y verificado con `alembic current`.
- [ ] `/api/health` responde 200.
- [ ] Primer super administrador creado.
- [ ] Copia de seguridad automática funcionando **y una restauración probada**.
- [ ] Un solo trabajador de la API (ancla del reloj), o la ancla movida a la base.
- [ ] `X-Real-IP` presente en el proxy (para `audit_logs.ip_address`).
- [ ] Alerta de reloj sospechoso configurada.
- [ ] Los registros llegan al sistema centralizado.
- [ ] Sin acceso directo a PostgreSQL desde Internet.