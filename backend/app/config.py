"""Configuración de Parkium Web (docs/08 §8.2).

Lee el entorno con el prefijo PARKIUM_ y expone un objeto único.
En desarrollo todo funciona sin variables opcionales.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from zoneinfo import ZoneInfo

DEFAULT_SITE_TZ = ZoneInfo("America/Bogota")

# Constantes de negocio (docs/07 §7.2 — se conservan idénticas al original)
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_SAFE = {(16384, 8, 1)}
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 256
SESSION_DURATION = 12 * 3600  # 12 h, en segundos
DEFAULT_SITE_ID = 1
SCHEMA_VERSION = 3

# Tarifas
BILLING_SCHEMES = (
    "MINUTE", "HOUR", "HOUR_FRACTION",
    "FLAT_ENTRY", "BLOCKS", "DAY", "NIGHT",
)

# Fechas y horas
HORA_FMT = "%H:%M"


def _root_data_dir() -> Path:
    d = Path(os.environ.get("PARKIUM_DATA_DIR", Path(__file__).resolve().parents[2] / "runtime"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class Settings:
    def __init__(self) -> None:
        self.entorno = os.environ.get("PARKIUM_ENTORNO", "desarrollo")
        self.sqlite_path = Path(
            os.environ.get("PARKIUM_SQLITE_PATH", _root_data_dir() / "parkium.db")
        )
        self.duracion_sesion_horas = int(os.environ.get("PARKIUM_DURACION_SESION_HORAS", "12"))
        self.longitud_minima_contrasena = int(
            os.environ.get("PARKIUM_LONGITUD_MINIMA_CONTRASENA", str(PASSWORD_MIN_LENGTH))
        )
        self.origenes_permitidos = os.environ.get(
            "PARKIUM_ORIGENES_PERMITIDOS", "http://localhost:5173,http://localhost:4173"
        ).split(",")
        self.url_fuente_hora = os.environ.get(
            "PARKIUM_URL_FUENTE_HORA", "https://www.google.com/generate_204"
        )
        self.espera_maxima_fuente_hora = float(
            os.environ.get("PARKIUM_ESPERA_MAXIMA_FUENTE_HORA", "6.0")
        )
        self.url_publica_base = os.environ.get("PARKIUM_URL_PUBLICA_BASE", "")
        # docs/12 §4: facturación electrónica SIEMPRE desactivada.
        self.proveedor_facturacion = "DISABLED"
        self.impresora_termica = os.environ.get("PARKIUM_IMPRESORA_TERMICA")

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.origenes_permitidos if o.strip()]

    @property
    def cookie_secure(self) -> bool:
        # docs/07 §7.3: Secure obligatorio en producción (sólo HTTPS)
        return self.entorno == "produccion"

    @property
    def is_windows_server(self) -> bool:
        return sys.platform == "win32"


settings = Settings()
