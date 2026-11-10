"""Crea el primer super administrador (docs/08 §8.8, docs/07 §7.5).

Uso:
    python scripts/create_first_admin.py --usuario bsmb --nombre "Root" --contraseña ...

La recuperación de contraseña administrativa NO se expone por HTTP
(docs/12 §2, recomendación A): se hace con este script en la consola del servidor.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import ensure_schema, health  # noqa: E402
from app.domain import authentication as auth_mod  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Crea el super administrador de arranque.")
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--nombre", required=True)
    parser.add_argument("--contraseña", required=False)
    args = parser.parse_args()
    ensure_schema()
    import getpass
    contraseña = args.contraseña or getpass.getpass("Contraseña: ")

    if auth_mod.has_users():
        usuario = auth_mod.get_user(1)
        print("Ya existen usuarios. Para restablecer una cuenta administrativa use: ")
        print("    python scripts/reset-admin.py <usuario>")
        print(f"{health()}")
        return 1
    user = auth_mod.create_first_administrator(args.usuario, contraseña, args.nombre)
    print(f"Super administrador creado: {user['username']} ({user['full_name']})")
    print(health())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
