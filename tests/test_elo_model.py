"""Tests del modelo Elo (Fase 6). Sintéticos, sin red ni BD."""

import math

import pytest

from src.models.elo_model import EloModel, expected_score


def test_expected_score_basic():
    assert expected_score(1800, 1800) == pytest.approx(0.5)
    # +400 Elo → ~0.909
    assert expected_score(2200, 1800) == pytest.approx(1 / (1 + 10 ** -1), abs=1e-9)
    # Monótona: más rating local → mayor W_e.
    assert expected_score(1900, 1800) > expected_score(1800, 1800)


def test_host_bonus():
    base = expected_score(1800, 1800)
    home_host = expected_score(1800, 1800, host_side="home")
    away_host = expected_score(1800, 1800, host_side="away")
    assert home_host > base  # +100 Elo al local
    assert away_host < base  # ventaja al visitante
    assert home_host == pytest.approx(1 - away_host)


def test_fit_draw_rates_recovers_synthetic():
    # Construir partidos donde |dr| pequeño empata el 40%, grande el 5%.
    matches = []
    for _ in range(2000):
        matches.append((20, True))   # |dr|=20 bin 0
        matches.append((20, False))
    for _ in range(2000):
        matches.append((600, True))  # |dr|=600 bin 12
        matches.append((600, False))
    # Forzar proporciones distintas.
    matches = [(20, i % 5 == 0) for i in range(2000)] + [(600, i % 20 == 0) for i in range(2000)]
    model = EloModel(bin_width=50).fit_draw_rates(matches, prior_weight=1.0)
    low = model._draw_prob(20)
    high = model._draw_prob(600)
    assert low > high  # menos empates cuando hay más diferencia
    assert 0.15 < low < 0.25
    assert high < 0.10


def test_predict_1x2_sums_to_one_and_favors_stronger():
    model = EloModel()
    p = model.predict_1x2(2000, 1700)
    assert sum(p.values()) == pytest.approx(1.0)
    assert p["home"] > p["away"]

    # Equipos iguales sin host → simétrico.
    eq = model.predict_1x2(1800, 1800)
    assert eq["home"] == pytest.approx(eq["away"])

    # Host desplaza prob hacia el anfitrión.
    host = model.predict_1x2(1800, 1800, host_side="home")
    assert host["home"] > host["away"]


def test_serialization_roundtrip():
    model = EloModel(bin_width=50).fit_draw_rates([(10, True), (10, False), (500, False)])
    restored = EloModel.from_dict(model.to_dict())
    assert restored.bin_width == model.bin_width
    assert restored.predict_1x2(1900, 1850) == model.predict_1x2(1900, 1850)
