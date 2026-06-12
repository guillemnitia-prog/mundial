"""Tests del dimensionamiento de stake (≥20% / ≥10 €, tope 25%)."""

import pytest

from src.bankroll.kelly import (
    assign_recommended_stake,
    compute,
    recommended_fraction,
    user_stake,
)
from src.db.schema import Prediction


def test_recommended_fraction_is_floor_pct():
    # La fracción nominal recomendada es el suelo de política (20%), user-independent.
    assert recommended_fraction(0.78, 1.6) == pytest.approx(0.20)


def test_user_stake_20pct_on_normal_balance():
    s = user_stake(50.0)
    assert s["eur"] == pytest.approx(10.0)   # max(20% de 50, 10€) = 10
    assert s["pct"] == pytest.approx(0.20)
    assert s["bettable"] is True

    s2 = user_stake(200.0)
    assert s2["eur"] == pytest.approx(40.0)   # 20% de 200
    assert s2["pct"] == pytest.approx(0.20)


def test_user_stake_min_10_dominates_on_low_balance():
    # 30 €: 20% = 6 → sube a 10 €; el tope 25% (7,5) es menor que el mínimo, manda 10 €.
    s = user_stake(30.0)
    assert s["eur"] == pytest.approx(10.0)
    assert s["bettable"] is True


def test_user_stake_below_minimum_not_bettable():
    s = user_stake(8.0)
    assert s["bettable"] is False
    assert s["too_small"] is True
    assert "10" in s["message"]


def test_compute_shortcut():
    s = compute(0.78, 1.6, 50.0)
    assert s["eur"] == pytest.approx(10.0)


def test_assign_recommended_stake_sets_floor_fraction():
    p = Prediction(match_id=1, market="1x2", outcome="home", model_prob=0.78,
                   fair_prob=0.6, offered_odds=1.6, ev=0.2)
    frac = assign_recommended_stake(p)
    assert frac == pytest.approx(0.20)
    assert p.recommended_stake == pytest.approx(0.20)
