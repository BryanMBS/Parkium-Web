"""Restablece la contraseña de una cuenta administrativa desde la consola
del servidor (docs/12 §2 — opción A: NO exponer por HTTP)."""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import ensure_schema  # noqa: E402
from app.domain import authentication as auth_mod  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python scripts/reset-admin.py <usuario>")
        return 2
    ensure_schema()
    try:
        auth_mod.reset_administrator_password(sys.argv[1], getpass.getpass("Nueva contraseña: "))
        print("Contraseña restablecida y sesiones revocadas (PASSWORD_RESET_LOCAL).")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
