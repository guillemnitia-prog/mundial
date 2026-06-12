"""Configuración central de WorldCup Betting Analyzer.

Carga variables de entorno desde `.env` (si existe) y expone los parámetros de dominio
con defaults seguros tomados de `.env.example`. NUNCA se versiona `.env`.

Las reglas no negociables (EV>0, cuota >= 1.40, 1/4 Kelly con tope 5%) dependen de estos
valores; ver CLAUDE.md y DECISIONS.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Raíz del proyecto (un nivel por encima de src/).
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga .env si está presente; en su ausencia se usan los defaults de abajo.
load_dotenv(BASE_DIR / ".env")


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _get_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    return raw if raw not in (None, "") else default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    """Parámetros de dominio y conexión. Inmutable una vez cargado."""

    # --- APIs de datos (vacías por defecto; se rellenan en .env) ---
    football_data_token: str = ""
    odds_api_key: str = ""
    oddspapi_key: str = ""
    api_football_key: str = ""

    # --- Notificaciones push (VAPID) ---
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # --- Auth ---
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 días
    cookie_name: str = "access_token"      # cookie httpOnly que transporta el JWT
    cookie_secure: bool = False            # True en producción (HTTPS)
    cookie_samesite: str = "lax"           # lax en dev; revisar para cross-site en prod
    frontend_origin: str = "http://localhost:3000"  # origen de la PWA Next.js (CORS)

    # --- Parámetros de dominio (reglas no negociables) ---
    min_odds: float = 1.40       # cuota decimal mínima de los pronósticos
    kelly_fraction: float = 0.25  # 1/4 Kelly
    max_stake_pct: float = 0.05   # tope 5% del bankroll por apuesta
    group_bankroll: float = 350.0  # 7 amigos x 50 €

    # --- Datos ---
    database_url: str = "sqlite:///data/worldcup.db"
    odds_region: str = "eu"  # The Odds API no tiene región ES; eu como proxy
    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_competition: str = "WC"  # FIFA World Cup

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            football_data_token=_get_str("FOOTBALL_DATA_TOKEN", ""),
            odds_api_key=_get_str("ODDS_API_KEY", ""),
            oddspapi_key=_get_str("ODDSPAPI_KEY", ""),
            api_football_key=_get_str("API_FOOTBALL_KEY", ""),
            vapid_public_key=_get_str("VAPID_PUBLIC_KEY", ""),
            vapid_private_key=_get_str("VAPID_PRIVATE_KEY", ""),
            vapid_subject=_get_str("VAPID_SUBJECT", "mailto:admin@example.com"),
            jwt_secret=_get_str("JWT_SECRET", ""),
            jwt_algorithm=_get_str("JWT_ALGORITHM", "HS256"),
            jwt_expire_minutes=_get_int("JWT_EXPIRE_MINUTES", 10080),
            cookie_name=_get_str("COOKIE_NAME", "access_token"),
            cookie_secure=_get_bool("COOKIE_SECURE", False),
            cookie_samesite=_get_str("COOKIE_SAMESITE", "lax"),
            frontend_origin=_get_str("FRONTEND_ORIGIN", "http://localhost:3000"),
            min_odds=_get_float("MIN_ODDS", 1.40),
            kelly_fraction=_get_float("KELLY_FRACTION", 0.25),
            max_stake_pct=_get_float("MAX_STAKE_PCT", 0.05),
            group_bankroll=_get_float("GROUP_BANKROLL", 350.0),
            database_url=_get_str("DATABASE_URL", "sqlite:///data/worldcup.db"),
            odds_region=_get_str("ODDS_REGION", "eu"),
            football_data_base_url=_get_str("FOOTBALL_DATA_BASE_URL", "https://api.football-data.org/v4"),
            football_data_competition=_get_str("FOOTBALL_DATA_COMPETITION", "WC"),
        )


# Instancia global de solo lectura.
settings = Settings.load()
