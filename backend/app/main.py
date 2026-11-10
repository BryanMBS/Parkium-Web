"""Parkium Web — API FastAPI (docs/02 §2.1, docs/05 §1).

Middleware de errores que traduce cada excepción de dominio al contrato
de docs/04 §4.1; CORS restringido; cookie de sesión HttpOnly.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db
from .config import settings
from .domain.errors import DomainError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("parkium")

app = FastAPI(title="Parkium Web", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def errors_and_headers(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except DomainError as e:
        response = JSONResponse(
            status_code=e.status,
            content={"codigo": e.codigo, "mensaje": e.mensaje, "detalle": e.detalle},
        )
    except Exception:
        # errores al cliente sin rastro de pila (docs/05 §11)
        log.exception("[%s] error interno en %s", request_id, request.url.path)
        response = JSONResponse(status_code=500,
                                content={"codigo": "interno", "mensaje": "Fallo no previsto.",
                                         "detalle": {"id_peticion": request_id}})
    response.headers["X-Request-Id"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Cache-Control", "no-store")
    if request.url.path.startswith("/api/"):
        log.info("[%s] %s %s -> %s %.1f ms", request_id, request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
    return response


@app.on_event("startup")
def on_startup():
    db.ensure_schema()                      # docs/09 tarea 1.6
    from .domain import time_integrity
    time_integrity._ensure_anchor()         # docs/09 tarea 5.1
    from .domain import authentication as auth_mod
    auth_mod.cleanup_expired_sessions()     # docs/01 §1.4
    log.info("Parkium Web arrancada (entorno=%s, motor=%s)", settings.entorno, "sqlite")


@app.on_event("shutdown")
def on_shutdown():
    from .domain import authentication as auth_mod
    auth_mod.cleanup_expired_sessions()


from .api import admin, auth, cash, health, history, parking, platform, receipts, reports, subscriptions  # noqa: E402

# recibos públicos FUERA de /api (docs/04 §4.13)
app.include_router(receipts.router)
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(parking.router)
app.include_router(history.router)
app.include_router(receipts.router)
app.include_router(cash.router)
app.include_router(subscriptions.router)
app.include_router(reports.router)
app.include_router(admin.router)
app.include_router(platform.router)   # Fase 2: módulo de plataforma

# navegación y páginas de estado para la API
API_ROUTER_DOCS = {"como_usar": "La sesión viaja en la cookie HttpOnly parkium_sesion."}


@app.get("/api")
def root():
    return {"servicio": "parkium-web", "estado": "ok", **API_ROUTER_DOCS}
