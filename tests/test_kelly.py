"""Tests de dimensionamiento de stake con ¼ Kelly (Fase 9)."""

import pytest

from src.bankroll.kelly import (
    assign_recommended_stake,
    compute,
    kelly_fraction,
    recommended_fraction,
    user_stake,
)
from src.db.schema import Prediction


def test_kelly_fraction():
    # p=0.6 @ odds 2.0: b=1, f=(0.6-0.4)/1=0.2
    assert kelly_fraction(0.6, 2.0) == pytest.approx(0.2)
    # sin edge: p=0.5 @ 2.0 → 0
    assert kelly_fraction(0.5, 2.0) == 0.0
    assert kelly_fraction(0.9, 1.0) == 0.0  # odds<=1


def test_recommended_fraction_quarter_and_cap():
    # ¼ Kelly: 0.2·0.25 = 0.05 (justo en el tope 5%)
    assert recommended_fraction(0.6, 2.0) == pytest.approx(0.05)
    # Edge enorme → recortado al 5%.
    assert recommended_fraction(0.95, 3.0) == pytest.approx(0.05)
    # Sin edge → 0.
    assert recommended_fraction(0.5, 2.0) == 0.0


def test_user_stake_eur_and_pct():
    s = user_stake(50.0, 0.05)
    assert s["eur"] == pytest.approx(2.5)
    assert s["pct"] == pytest.approx(0.05)
    assert s["bettable"] is True
    assert s["halved"] is False


def test_user_stake_halving_below_half_initial():
    # Saldo 20 < 25 (50% de 50) → halving: fracción 0.05→0.025
    s = user_stake(20.0, 0.05, initial_balance=50.0)
    assert s["halved"] is True
    assert s["pct"] == pytest.approx(0.025)
    assert s["eur"] == pytest.approx(0.5)
    # 0.5 € < MIN_STAKE_EUR (1.0) → demasiado pequeña.
    assert s["too_small"] is True
    assert s["bettable"] is False
    assert s["message"]


def test_user_stake_too_small():
    s = user_stake(10.0, 0.05)  # 0.5 € < 1.0
    assert s["too_small"] is True
    assert s["bettable"] is False


def test_compute_shortcut():
    s = compute(0.6, 2.0, 50.0)
    assert s["eur"] == pytest.approx(2.5)
    assert s["bettable"] is True


def test_assign_recommended_stake_sets_fraction():
    p = Prediction(match_id=1, market="1x2", outcome="home", model_prob=0.6,
                   fair_prob=0.5, offered_odds=2.0, ev=0.2)
    frac = assign_recommended_stake(p)
    assert frac == pytest.approx(0.05)
    assert p.recommended_stake == pytest.approx(0.05)
