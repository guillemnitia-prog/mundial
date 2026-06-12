"""Tests del modelo Dixon-Coles (Fase 5). Datos sintéticos, sin red ni BD."""

import math

import numpy as np
import pytest

from src.models.dixon_coles import DixonColesModel, decay_weights, tau


# --- helpers puros ---------------------------------------------------------

def test_tau_special_cells():
    lam, mu, rho = 1.3, 1.1, -0.05
    assert tau(0, 0, lam, mu, rho) == pytest.approx(1 - lam * mu * rho)
    assert tau(0, 1, lam, mu, rho) == pytest.approx(1 + lam * rho)
    assert tau(1, 0, lam, mu, rho) == pytest.approx(1 + mu * rho)
    assert tau(1, 1, lam, mu, rho) == pytest.approx(1 - rho)
    # Fuera de las 4 celdas → 1.
    assert tau(2, 3, lam, mu, rho) == 1.0
    assert tau(0, 2, lam, mu, rho) == 1.0


def test_decay_weights_monotonic():
    ages = np.array([0, 30, 365, 730])
    w = decay_weights(ages, xi=0.001)
    assert w[0] == pytest.approx(1.0)
    assert np.all(np.diff(w) < 0)  # más antiguo → menos peso
    # xi=0 → todos 1.
    assert np.allclose(decay_weights(ages, xi=0.0), 1.0)


# --- generación sintética --------------------------------------------------

def _simulate(seed=42, n_matches=4000):
    """Genera partidos desde strengths conocidos (forma aditiva)."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(8)]
    true_atk = {t: v for t, v in zip(teams, np.linspace(0.6, -0.6, len(teams)))}
    true_def = {t: v for t, v in zip(teams, np.linspace(-0.4, 0.4, len(teams)))}
    mu, gamma = 0.1, 0.3

    rows = []
    for _ in range(n_matches):
        h, a = rng.choice(teams, size=2, replace=False)
        neutral = bool(rng.integers(0, 2))
        gh = 0.0 if neutral else gamma
        lam = math.exp(mu + true_atk[h] + true_def[a] + gh)
        mua = math.exp(mu + true_atk[a] + true_def[h])
        hg = rng.poisson(lam)
        ag = rng.poisson(mua)
        rows.append((h, a, int(hg), int(ag), None, neutral))
    return rows, true_atk, true_def, gamma


def _centered(d):
    vals = np.array(list(d.values()))
    return {k: v - vals.mean() for k, v in d.items()}


# --- recuperación de parámetros -------------------------------------------

def test_recovers_synthetic_strengths():
    rows, true_atk, true_def, gamma = _simulate()
    model = DixonColesModel().fit(rows)

    teams = sorted(true_atk)
    est_atk = _centered(model.attack)
    tru_atk = _centered(true_atk)
    est_def = _centered(model.defense)
    tru_def = _centered(true_def)

    corr_atk = np.corrcoef([est_atk[t] for t in teams], [tru_atk[t] for t in teams])[0, 1]
    corr_def = np.corrcoef([est_def[t] for t in teams], [tru_def[t] for t in teams])[0, 1]
    assert corr_atk > 0.9
    assert corr_def > 0.9
    assert model.home_adv > 0.1  # ventaja local aprendida (verdadera 0.3)

    # El equipo más fuerte (T0) gana al más débil (T7) con probabilidad alta.
    mk = model.predict_markets("T0", "T7", neutral=True)
    assert mk["1x2"]["home"] > mk["1x2"]["away"]


# --- consistencia de mercados ----------------------------------------------

def test_market_probabilities_consistent():
    rows, *_ = _simulate()
    model = DixonColesModel().fit(rows)

    mat = model.score_matrix("T2", "T5", neutral=True)
    assert mat.sum() == pytest.approx(1.0, abs=1e-6)

    mk = model.predict_markets("T2", "T5", neutral=True, ou_lines=(1.5, 2.5))
    p = mk["1x2"]
    assert p["home"] + p["draw"] + p["away"] == pytest.approx(1.0, abs=1e-6)
    assert mk["over_under"]["over_2.5"] + mk["over_under"]["under_2.5"] == pytest.approx(1.0, abs=1e-6)
    assert 0.0 <= mk["btts"]["yes"] <= 1.0
    assert len(mk["correct_score"]) == 5


# --- ventaja local ----------------------------------------------------------

def test_home_advantage_only_when_not_neutral():
    rows, *_ = _simulate()
    model = DixonColesModel().fit(rows)

    # Mismo equipo en ambos lados → en neutral, 1X2 simétrico (home≈away).
    neutral = model.predict_markets("T3", "T3", neutral=True)["1x2"]
    assert neutral["home"] == pytest.approx(neutral["away"], abs=1e-6)

    # No neutral → el local (con γ) tiene más prob. que el visitante.
    non_neutral = model.predict_markets("T3", "T3", neutral=False)["1x2"]
    assert non_neutral["home"] > non_neutral["away"]

    # host_side='away' → la ventaja se aplica al visitante.
    away_host = model.predict_markets("T3", "T3", neutral=False, host_side="away")["1x2"]
    assert away_host["away"] > away_host["home"]


# --- serialización y determinismo -------------------------------------------

def test_serialization_roundtrip():
    rows, *_ = _simulate(n_matches=1500)
    model = DixonColesModel().fit(rows)
    restored = DixonColesModel.from_dict(model.to_dict())
    a = model.predict_markets("T1", "T6", neutral=False)["1x2"]
    b = restored.predict_markets("T1", "T6", neutral=False)["1x2"]
    assert a == b


def test_fit_is_deterministic():
    rows, *_ = _simulate(n_matches=1500)
    m1 = DixonColesModel().fit(rows)
    m2 = DixonColesModel().fit(rows)
    assert m1.attack == m2.attack
    assert m1.home_adv == m2.home_adv
