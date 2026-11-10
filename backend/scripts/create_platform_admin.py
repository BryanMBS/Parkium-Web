"""Crea el administrador de PLATAFORMA (Fase 2) — usuario fuera de todo tenant.

Uso:
    python scripts/create_platform_admin.py \
        --usuario superadmin@parkium.co --nombre "Super Admin" [--contraseña ...]

- Si no se pasa --contraseña se toma de la variable de entorno
  PARKIUM_ADMIN_PLATAFORMA_CONTRASENA o se pide por consola (getpass).
  Nunca queda una contraseña hardcodeada en el repositorio.
- El usuario se crea con role_id del rol PLATFORM_ADMIN y tenant_id NULL:
  NO puede usar las rutas operativas, sólo /api/platform/*.
- Nota: el patrón de usuarios del tenant (^[A-Za-z0-9._-]{3,60}$) no admite
  `@`; para el admin de plataforma se acepta también un email válido
  (decisión anotada: es una cuenta de espacio separado).
"""
import argparse
import getpass
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import ensure_schema, query_one, transaction  # noqa: E402
from app.domain import authentication as auth_mod  # noqa: E402

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _validar_usuario_plataforma(usuario: str) -> None:
    if _EMAIL_RE.match(usuario or ""):
        return
    auth_mod._validar_usuario(usuario)  # patrón estándar del sistema


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crea el administrador de plataforma (tenant_id NULL).")
    parser.add_argument("--usuario", default="superadmin@parkium.co")
    parser.add_argument("--nombre", default="Super Admin")
    parser.add_argument("--contraseña", required=False)
    args = parser.parse_args()

    contraseña = (args.contraseña
                  or os.environ.get("PARKIUM_ADMIN_PLATAFORMA_CONTRASENA")
                  or getpass.getpass("Contraseña del admin de plataforma: "))
    _validar_usuario_plataforma(args.usuario)
    auth_mod._validar_contraseña(contraseña)

    ensure_schema()
    rol = query_one("SELECT id FROM roles WHERE code = 'PLATFORM_ADMIN'")
    if not rol:
        print("ERROR: no existe el rol PLATFORM_ADMIN.")
        print("Corre primero: python scripts/migrate_multi_tenant.py")
        return 1
    if query_one("SELECT id FROM users WHERE username = ?", (args.usuario,)):
        print(f"ERROR: ya existe un usuario «{args.usuario}».")
        return 1

    with transaction() as conn:
        cur = conn.execute(
            "INSERT INTO users (role_id, tenant_id, username, password_hash, "
            "full_name, must_change_password) VALUES (?,?,?,?,?,0)",
            (rol["id"], None, args.usuario, auth_mod.hash_password(contraseña),
             args.nombre))
        user_id = int(cur.lastrowid or 0)
        conn.execute(
            "INSERT INTO audit_logs (user_id, tenant_id, entity_type, entity_id, "
            "action, after_data) VALUES (?,?,?,?,?,?)",
            (user_id, None, "user", user_id, "PLATFORM_ADMIN_CREATED",
             json.dumps({"username": args.usuario})))

    print(f"Admin de plataforma creado: {args.usuario} (id {user_id}) — tenant_id NULL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
