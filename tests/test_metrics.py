"""Tests de métricas RPS/Brier (Fase 7)."""

import pytest

from src.models.metrics import brier, result_outcome, rps


def test_rps_perfect_and_uniform():
    assert rps({"home": 1.0, "draw": 0.0, "away": 0.0}, "home") == pytest.approx(0.0)
    # Uniforme, resultado home: 5/18.
    assert rps({"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}, "home") == pytest.approx(5 / 18)


def test_rps_orders_matter():
    # Predecir 'away' cuando gana 'home' es peor que predecir 'draw' (ordinal).
    far = rps({"home": 0.0, "draw": 0.0, "away": 1.0}, "home")
    near = rps({"home": 0.0, "draw": 1.0, "away": 0.0}, "home")
    assert far > near


def test_brier():
    assert brier({"home": 1.0, "draw": 0.0, "away": 0.0}, "home") == pytest.approx(0.0)
    assert brier({"home": 1 / 3, "draw": 1 / 3, "away": 1 / 3}, "home") == pytest.approx(2 / 3)


def test_result_outcome():
    assert result_outcome(2, 0) == "home"
    assert result_outcome(1, 1) == "draw"
    assert result_outcome(0, 3) == "away"
