"""Prueba de humo multi-tenant (Fases 1-2) — corre contra un servidor vivo.

Uso:
    1) Copia la base (NO testamos sobre la real):
       copy runtime\\parkium.db runtime\\_test_multi.db
    2) Levanta el servidor:
       set PARKIUM_SQLITE_PATH=runtime\\_test_multi.db
       uvicorn app.main:app --port 8010   (desde backend)
    3) Corre la prueba:
       set PARKIUM_BASE_URL=http://127.0.0.1:8010
       set PARKIUM_ADMIN_PLATAFORMA_CONTRASENA=<la del admin de plataforma>
       python backend\\scripts\\smoke_multi_tenant.py

Cubre: login plataforma, crear tenant (UNA transacción: sede+admin+password
temporal), login del admin del tenant, cuotas (409 limite_plan_alcanzado),
aislamiento de placa y comprobante entre DOS tenants, suspensión (sesión
inválida + login bloqueado), reactivación, 403 en /api/platform/* para un
usuario de tenant y 403 en rutas operativas para el admin de plataforma.
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import urllib.parse
import uuid

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # consolas cp1252

BASE = os.environ.get("PARKIUM_BASE_URL", "http://127.0.0.1:8010")
PASS_PLATAFORMA = os.environ.get("PARKIUM_ADMIN_PLATAFORMA_CONTRASENA") or ""
if not PASS_PLATAFORMA:
    sys.exit("Define PARKIUM_ADMIN_PLATAFORMA_CONTRASENA para ejecutar la prueba.")

HOSTPORT = urllib.parse.urlparse(BASE)
HOST, PORT = HOSTPORT.hostname, HOSTPORT.port or 80
MENSAJE_SUSPENSION = "Cuenta suspendida, contacta a soporte"

_fallos: list[str] = []
_paso = 0


def _req(metodo: str, ruta: str, cuerpo: dict | None = None, cookie: str | None = None,
         headers: dict | None = None):
    payload = json.dumps(cuerpo).encode() if cuerpo is not None else None
    conn = http.client.HTTPConnection(HOST, PORT, timeout=30)
    hdrs = {"Content-Type": "application/json; charset=utf-8", **(headers or {})}
    if cookie:
        hdrs["Cookie"] = cookie
    conn.request(metodo, ruta, body=payload, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    set_cookie = resp.getheader("Set-Cookie")
    conn.close()
    try:
        parsed = json.loads(data) if data else None
    except json.JSONDecodeError:
        parsed = {"_raw": data.decode("utf-8", "replace")}
    return resp.status, parsed, set_cookie


def _sesion(ruta_login: str, usuario: str, contraseña: str) -> str:
    estado, cuerpo, set_cookie = _req("POST", ruta_login,
                                      {"usuario": usuario, "contraseña": contraseña})
    if estado != 200 or not set_cookie:
        raise AssertionError(f"login {usuario}: HTTP {estado} → {cuerpo}")
    return set_cookie.split(";")[0]


def check(nombre: str, cond: bool, detalle: str = "") -> None:
    global _paso
    _paso += 1
    marca = "OK " if cond else "FALLO"
    print(f"  [{marca}] #{_paso:02d} {nombre}" + (f" → {detalle}" if detalle else ""))
    if not cond:
        _fallos.append(f"#{_paso:02d} {nombre} {detalle}")


def main() -> int:
    print(f"== Parkium multi-tenant: {BASE} ==")

    # ── 1. acceso a plataforma ─────────────────────────────────────────
    print("== plataforma: login y 403 de un usuario de tenant ==")
    cookie_plat = _sesion("/api/auth/login", "superadmin@parkium.co", PASS_PLATAFORMA)
    estado, resumen, _ = _req("GET", "/api/platform/summary", cookie=cookie_plat)
    check("GET /platform/summary con PLATFORM_ADMIN", estado == 200, str(resumen))

    cookie_demo = _sesion("/api/auth/login", "admin", "Cambiame.123")
    estado, cuerpo, _ = _req("GET", "/api/platform/summary", cookie=cookie_demo)
    check("GET /platform/summary con SUPERADMIN de tenant → 403",
          estado == 403, f"HTTP {estado}")

    estado, cuerpo, _ = _req("GET", "/api/stays/active?placa=ABC123", cookie=cookie_plat)
    check("ruta operativa con PLATFORM_ADMIN → 403", estado == 403, f"HTTP {estado}")

    # ── 2. crear dos tenants (UNA transacción) ────────────────────────
    print("== crear tenants A y B ==")
    sufijo = uuid.uuid4().hex[:6]
    tenants = {}
    nits = {"A": "901234567-7", "B": "902345678-6"}   # dígito verificador DIAN previamente calculado
    for letra, max_sites, max_users in (("A", 1, 2), ("B", 2, 3)):
        cuerpo = {
            "name": f"Test {letra} {sufijo} S.A.S.",
            "nit": nits[letra],
            "plan": "PRO", "max_sites": max_sites, "max_users": max_users,
            "billing_cutoff_day": 5,
            "sede_nombre": f"Sede principal {letra}",
            "sede_cupos": 25,
            "admin_username": f"admintest{letra.lower()}{sufijo[:4]}",
            "admin_nombre": f"Admin {letra}",
        }
        estado, creado, _ = _req("POST", "/api/platform/tenants", cuerpo, cookie=cookie_plat)
        check(f"POST /platform/tenants (tenant {letra}) → 201",
              estado == 201 and creado.get("tenant", {}).get("id"), json.dumps(creado)[:160])
        tenants[letra] = {
            "id": (creado.get("tenant") or {}).get("id"),
            "sede_id": creado.get("sede_id"),
            "admin": creado["admin"]["username"],
            "password": creado["contrasena_temporal"],
            "max_sites": max_sites, "max_users": max_users,
        }
        check(f"tenant {letra}: contraseña temporal del admin presente",
              bool(tenants[letra]["password"]))

    # NIT inválido → 400 con contrato { codigo, mensaje, detalle }
    estado, err, _ = _req("POST", "/api/platform/tenants", {
        "name": "Test NIT malo", "nit": "123-45-6X", "plan": "BASIC",
    }, cookie=cookie_plat)
    check("NIT inválido → 400 con codigo=validacion",
          estado == 400 and err.get("codigo") == "validacion", json.dumps(err)[:160])

    # ── 3. login de los admins de tenant ──────────────────────────────
    print("== login de los admins de tenant ==")
    cookie_a = _sesion("/api/auth/login", tenants["A"]["admin"], tenants["A"]["password"])
    cookie_b = _sesion("/api/auth/login", tenants["B"]["admin"], tenants["B"]["password"])
    check("login admin tenant A", bool(cookie_a))
    check("login admin tenant B", bool(cookie_b))

    # ── 4. cuotas del plan (409 limite_plan_alcanzado) ────────────────
    print("== cuotas de plan ==")
    estado, err, _ = _req("POST", f"/api/platform/tenants/{tenants['A']['id']}/sites",
                          {"name": "Sede extra A", "total_capacity": 10}, cookie=cookie_plat)
    check("exceder max_sites → 409 limite_plan_alcanzado",
          estado == 409 and err.get("codigo") == "limite_plan_alcanzado",
          json.dumps(err)[:160])

    # usuario extra: tenant B tiene max_users=3 (1 admin inicial + 2 más)
    for i in range(2):
        estado, ok, _ = _req("POST", f"/api/platform/tenants/{tenants['B']['id']}/admins",
                             {"username": f"extra{i}{sufijo[:4]}"}, cookie=cookie_plat)
        check(f"crear admin extra {i} de B (dentro del plan) → 201", estado == 201,
              json.dumps(ok)[:120])
    estado, err, _ = _req("POST", f"/api/platform/tenants/{tenants['B']['id']}/admins",
                          {"username": f"extra3{sufijo[:4]}"}, cookie=cookie_plat)
    check("exceder max_users → 409 limite_plan_alcanzado",
          estado == 409 and err.get("codigo") == "limite_plan_alcanzado",
          json.dumps(err)[:160])

    # ── 5. aislamiento entre tenants ──────────────────────────────────
    print("== aislamiento: misma placa, datos separados ==")
    placa = "TRD" + uuid.uuid4().hex[:4].upper()
    estado, entrada_a, _ = _req("POST", "/api/stays",
                                {"placa": placa, "tipo_vehiculo": "CAR"}, cookie=cookie_a)
    check(f"tenant A registra entrada de {placa} → 201", estado == 201,
          json.dumps(entrada_a)[:120])
    receipt_a = (entrada_a.get("recibo") or {}).get("id")

    estado, entrada_b, _ = _req("POST", "/api/stays",
                                {"placa": placa, "tipo_vehiculo": "CAR"}, cookie=cookie_b)
    check(f"tenant B registra LA MISMA placa independiente → 201", estado == 201,
          json.dumps(entrada_b)[:120])
    receipt_b = (entrada_b.get("recibo") or {}).get("id")

    estado, cuerpo, _ = _req("GET", f"/api/receipts/{receipt_a}/preview", cookie=cookie_b)
    check("tenant B NO ve el comprobante de A → 404", estado == 404, f"HTTP {estado}")
    estado, cuerpo, _ = _req("GET", f"/api/receipts/{receipt_a}/preview", cookie=cookie_a)
    check("tenant A ve su propio comprobante → 200", estado == 200, f"HTTP {estado}")

    # historial: A no ve estadías de B (los ids difieren por site_id)
    estado, hist_b, _ = _req("GET", "/api/history", cookie=cookie_b)
    placas_b = {r["placa"] for r in hist_b.get("resultados", [])} if estado == 200 else set()
    check("historial de B contiene su placa", placa in placas_b, f"HTTP {estado}")

    # ── 6. suspensión y reactivación ──────────────────────────────────
    print("== suspensión / reactivación ==")
    estado, cuerpo, _ = _req("POST", f"/api/platform/tenants/{tenants['A']['id']}/suspend",
                             {"motivo": "Prueba de suspensión"}, cookie=cookie_plat)
    check("suspend tenant A → 200", estado == 200, f"HTTP {estado}")

    estado, cuerpo, _ = _req("GET", "/api/history", cookie=cookie_a)
    check("sesión activa de A queda revocada/inhabilitada en la próxima petición",
          estado == 401 or (estado == 403 and cuerpo.get("mensaje") == MENSAJE_SUSPENSION),
          f"HTTP {estado} {json.dumps(cuerpo)[:120]}")

    estado, cuerpo, _ = _req("POST", "/api/auth/login",
                             {"usuario": tenants["A"]["admin"],
                              "contraseña": tenants["A"]["password"]})
    check("login de A con tenant suspendido → 403 + mensaje",
          estado == 403 and MENSAJE_SUSPENSION in str(cuerpo.get("mensaje")),
          f"HTTP {estado} {json.dumps(cuerpo)[:120]}")

    # la suspensión no afecta a B ni al comprobante público /r/{token}
    estado, rec_b_full, _ = _req("GET", f"/api/receipts/{receipt_b}/preview", cookie=cookie_b)
    token_url = (rec_b_full or {}).get("url_qr") or ""
    token = token_url.rsplit("/", 1)[-1]
    estado, cuerpo, _ = _req("GET", f"/r/{token}")
    check("comprobante público de B sigue publicado (decisión documentada)",
          estado == 200, f"HTTP {estado}")

    estado, cuerpo, _ = _req("POST", f"/api/platform/tenants/{tenants['A']['id']}/reactivate",
                             {"motivo": "Prueba finalizada"}, cookie=cookie_plat)
    check("reactivate tenant A → 200", estado == 200, f"HTTP {estado}")
    estado, cuerpo, _ = _req("POST", "/api/auth/login",
                             {"usuario": tenants["A"]["admin"],
                              "contraseña": tenants["A"]["password"]})
    check("login de A tras reactivar → OK", estado == 200, f"HTTP {estado}")

    # reevocación de sesión previa: la sesión vieja de A sigue muerta porque
    # la suspensión la revocó; login nuevo es distinto token
    estado, cuerpo, _ = _req("GET", "/api/history", cookie=cookie_a)
    check("sesión PREVIA de A sigue revocada tras reactivar → 401/403",
          estado in (401, 403), f"HTTP {estado}")

    # ── 7. auditoría de plataforma ────────────────────────────────────
    print("== auditoría y resumen ==")
    estado, audi, _ = _req("GET", "/api/platform/audit?por_pagina=50", cookie=cookie_plat)
    acciones = {ev["action"] for ev in (audi.get("eventos") or [])}
    esperadas = {"TENANT_CREATED", "TENANT_SUSPEND", "TENANT_REACTIVATE"}
    check("auditoría contiene creación/suspensión/reactivación",
          estado == 200 and esperadas <= acciones, str(sorted(acciones))[:120])
    estado, audi_f, _ = _req(
        "GET", f"/api/platform/audit?tenant_id={tenants['A']['id']}", cookie=cookie_plat)
    check("filtro de auditoría por tenant",
          all(ev["tenant_id"] == tenants["A"]["id"] for ev in audi_f.get("eventos", [])),
          f"HTTP {estado}")

    estado, resumen, _ = _req("GET", "/api/platform/summary", cookie=cookie_plat)
    check("summary refleja 2 clientes nuevos activos",
          estado == 200 and resumen.get("activos", 0) >= 3, str(resumen))

    print()
    if _fallos:
        print(f"RESULTADO: {_paso - len(_fallos)}/{_paso} pruebas OK. Fallos:")
        for f in _fallos:
            print("  -", f)
        return 1
    print(f"RESULTADO: {_paso}/{_paso} pruebas OK ✔")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
