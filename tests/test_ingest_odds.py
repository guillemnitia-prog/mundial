"""Tests del ingest de The Odds API (Fase 8). Sin red: http_get falso + presupuesto."""

import dataclasses
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from src.config import settings
from src.db.schema import ApiUsage, Match, Odds, Team
from src.ingest.odds_api import OddsApiClient, OddsBudgetError, remaining_budget


def _patch_settings(monkeypatch, **overrides):
    """settings es frozen: se reemplaza el objeto del módulo odds_api con una copia."""
    monkeypatch.setattr("src.ingest.odds_api.settings", dataclasses.replace(settings, **overrides))

# Payload estilo The Odds API: un evento con h2h y totals.
SAMPLE_EVENTS = [
    {
        "home_team": "Mexico", "away_team": "South Africa",
        "commence_time": "2026-06-11T19:00:00Z",
        "bookmakers": [
            {"key": "book1", "markets": [
                {"key": "h2h", "outcomes": [
                    {"name": "Mexico", "price": 1.80},
                    {"name": "South Africa", "price": 4.50},
                    {"name": "Draw", "price": 3.40},
                ]},
                {"key": "totals", "outcomes": [
                    {"name": "Over", "price": 1.90, "point": 2.5},
                    {"name": "Under", "price": 1.90, "point": 2.5},
                ]},
            ]},
        ],
    },
    {  # evento que no está en nuestros matches → se ignora
        "home_team": "Nowhere", "away_team": "Elsewhere",
        "bookmakers": [{"key": "book1", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Nowhere", "price": 2.0}]}]}],
    },
]


def _seed_match(db):
    home = Team(name="Mexico", fifa_code="MEX")
    away = Team(name="South Africa", fifa_code="RSA")
    db.add_all([home, away])
    db.commit()
    m = Match(home_id=home.id, away_id=away.id, stage="group", status="scheduled",
              utc_date=datetime(2026, 6, 11, 19, tzinfo=timezone.utc))
    db.add(m)
    db.commit()
    return m


def test_ingest_normalizes_and_matches(db, monkeypatch):
    _patch_settings(monkeypatch, odds_api_key="test-key")
    m = _seed_match(db)
    calls = {"n": 0}

    def fake_http_get(url, params):
        calls["n"] += 1
        return SAMPLE_EVENTS

    client = OddsApiClient(http_get=fake_http_get)
    summary = client.ingest_odds(db)
    assert summary["events"] == 1  # solo el de Mexico
    # 1x2 (3) + over_under (2) = 5 filas normalizadas.
    assert db.execute(select(func.count(Odds.id))).scalar_one() == 5

    o = db.execute(select(Odds).where(Odds.market == "1x2", Odds.outcome == "home")).scalar_one()
    assert o.price == 1.80
    assert {r.outcome for r in db.execute(select(Odds).where(Odds.market == "over_under")).scalars()} == {
        "over_2.5", "under_2.5"
    }

    # Segunda pasada: caché fresca → sin red; upsert no duplica.
    client.ingest_odds(db)
    assert calls["n"] == 1
    assert db.execute(select(func.count(Odds.id))).scalar_one() == 5


def test_budget_counts_and_blocks(db, monkeypatch):
    # 3 mercados × 1 región → coste 3.
    _patch_settings(monkeypatch, odds_api_key="test-key",
                    odds_markets="h2h,totals,spreads", odds_region="eu")
    _seed_match(db)

    def fake_http_get(url, params):
        return SAMPLE_EVENTS

    client = OddsApiClient(http_get=fake_http_get)
    client.ingest_odds(db)
    usage = db.execute(select(ApiUsage)).scalar_one()
    assert usage.credits_used == 3  # markets×regions

    # Presupuesto casi agotado (4: queda 1 < coste 3) y caché expirada → debe cortar.
    _patch_settings(monkeypatch, odds_api_key="test-key",
                    odds_markets="h2h,totals,spreads", odds_region="eu", odds_monthly_budget=4)
    from src.db.schema import ApiCache
    cache = db.execute(select(ApiCache)).scalar_one()
    cache.expires_at = datetime(2000, 1, 1, tzinfo=timezone.utc)
    db.commit()

    with pytest.raises(OddsBudgetError):
        client.ingest_odds(db)
    assert remaining_budget(db) == 1  # no se gastó más
