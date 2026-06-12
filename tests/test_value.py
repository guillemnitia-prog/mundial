"""Tests de devig y selección de value bets (Fase 8)."""

import pytest

from src.value.devig import (
    consensus_implied,
    fair_probs_from_odds,
    implied_prob,
    remove_margin,
)
from src.value.ev import classify_confidence, ev, select_value_bets


# --- devig -----------------------------------------------------------------

def test_implied_prob():
    assert implied_prob(2.0) == 0.5
    assert implied_prob(4.0) == 0.25


def test_remove_margin_sums_to_one_and_overround():
    # 1X2 con overround: implícitas 0.5+0.3+0.3 = 1.1.
    implied = {"home": 0.5, "draw": 0.3, "away": 0.3}
    fair, overround = remove_margin(implied)
    assert sum(fair.values()) == pytest.approx(1.0)
    assert overround == pytest.approx(0.1)
    assert fair["home"] == pytest.approx(0.5 / 1.1)


def test_consensus_and_fair_from_odds():
    odds_by_book = {
        "book1": {"home": 2.0, "draw": 3.4, "away": 4.0},
        "book2": {"home": 2.1, "draw": 3.3, "away": 3.9},
    }
    cons = consensus_implied(odds_by_book)
    assert cons["home"] == pytest.approx((0.5 + 1 / 2.1) / 2)
    fair, overround = fair_probs_from_odds(odds_by_book)
    assert sum(fair.values()) == pytest.approx(1.0)
    assert overround > 0


# --- ev --------------------------------------------------------------------

def test_ev_formula():
    # prob 0.6 @ cuota 2.0: 0.6·1 − 0.4 = 0.2
    assert ev(0.6, 2.0) == pytest.approx(0.2)
    # prob justa (sin value): prob 0.5 @ 2.0 → EV 0
    assert ev(0.5, 2.0) == pytest.approx(0.0)


def test_classify_confidence():
    assert classify_confidence(0.80, 0.15) == "alta"
    assert classify_confidence(0.72, 0.15) == "media"   # prob < 0.75
    assert classify_confidence(0.80, 0.05) == "media"   # EV < 0.10


# --- select_value_bets -----------------------------------------------------

def _odds(odds, fair):
    return {"odds": odds, "fair_prob": fair}


def test_select_returns_value_picks_sorted():
    model = {"1x2": {"home": 0.78, "draw": 0.15, "away": 0.07},
             "over_under": {"over_2.5": 0.72}}
    market_odds = {
        "1x2": {"home": _odds(1.75, 0.62)},        # prob 0.78, cuota 1.75 → EV>0, alta
        "over_under": {"over_2.5": _odds(1.55, 0.66)},  # prob 0.72, cuota 1.55 → EV>0, media
    }
    picks = select_value_bets(model, market_odds)
    assert len(picks) == 2
    assert picks[0]["confidence"] == "alta"   # ordenado: alta primero
    assert picks[0]["outcome"] == "home"
    assert all(p["ev"] > 0 for p in picks)


def test_double_filter_excludes():
    model = {"1x2": {"home": 0.60, "draw": 0.20, "away": 0.20},  # prob<0.70 → fuera
             "over_under": {"over_2.5": 0.80}}
    market_odds = {
        "1x2": {"home": _odds(2.0, 0.5)},
        "over_under": {"over_2.5": _odds(1.30, 0.75)},  # cuota<1.40 → fuera
    }
    assert select_value_bets(model, market_odds) == []


def test_no_value_returns_empty():
    # Alta prob pero cuota demasiado baja → EV podría ser >0 pero cuota<1.40 lo descarta;
    # y un caso con EV<=0.
    model = {"1x2": {"home": 0.75, "draw": 0.15, "away": 0.10}}
    market_odds = {"1x2": {"home": _odds(1.20, 0.83)}}  # cuota<1.40
    assert select_value_bets(model, market_odds) == []


def test_never_more_than_two():
    model = {"1x2": {"home": 0.80, "draw": 0.75, "away": 0.78},
             "over_under": {"over_2.5": 0.79, "under_2.5": 0.77}}
    market_odds = {
        "1x2": {"home": _odds(1.6, 0.6), "draw": _odds(1.6, 0.6), "away": _odds(1.6, 0.6)},
        "over_under": {"over_2.5": _odds(1.6, 0.6), "under_2.5": _odds(1.6, 0.6)},
    }
    assert len(select_value_bets(model, market_odds)) == 2
