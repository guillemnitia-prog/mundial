"""Smoke test de la configuración base (Fase 1).

Verifica que `src.config` carga e impone los defaults de dominio coherentes con las reglas
no negociables de CLAUDE.md / DECISIONS.md.
"""

from src.config import Settings, settings


def test_settings_importable():
    assert settings is not None


def test_domain_defaults():
    s = Settings.load()
    # Reglas no negociables: filtro de cuota, 1/4 Kelly, tope 5%, bankroll de grupo.
    assert s.min_odds == 1.40
    assert s.kelly_fraction == 0.25
    assert s.max_stake_pct == 0.05
    assert s.group_bankroll == 350.0
    assert s.odds_region == "eu"  # proxy de Bet365.es/Sportium
    assert s.database_url.startswith("sqlite")


def test_settings_is_frozen():
    s = Settings.load()
    try:
        s.min_odds = 2.0  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("Settings debería ser inmutable (frozen dataclass)")
