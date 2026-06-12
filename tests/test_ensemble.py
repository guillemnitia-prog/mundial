"""Tests del ensemble DC+Elo y su entrenamiento (Fase 7). Datos sintéticos, sin red."""

from datetime import date

import pytest

from src.models.dixon_coles import DixonColesModel
from src.models.elo_model import EloModel
from src.models.ensemble import EnsembleModel, train


def _fit_small_dc():
    # A es más fuerte que B; algunos partidos para ajustar.
    matches = []
    for i in range(30):
        matches.append(("A", "B", 2, 0, date(2023, 1, 1), True))
        matches.append(("B", "A", 0, 1, date(2023, 6, 1), True))
    return DixonColesModel().fit(matches)


def test_weight_extremes_recover_components():
    dc = _fit_small_dc()
    elo = EloModel()
    ens_dc = EnsembleModel(dc=dc, elo=elo, weight=1.0)
    ens_elo = EnsembleModel(dc=dc, elo=elo, weight=0.0)

    dc_1x2 = dc.predict_markets("A", "B", neutral=True)["1x2"]
    elo_1x2 = elo.predict_1x2(1700, 1500, None)

    w1 = ens_dc.predict_1x2("A", "B", True, None, 1700, 1500)
    w0 = ens_elo.predict_1x2("A", "B", True, None, 1700, 1500)

    for k in ("home", "draw", "away"):
        assert w1[k] == pytest.approx(dc_1x2[k], abs=1e-9)
        assert w0[k] == pytest.approx(elo_1x2[k], abs=1e-9)


def test_predict_markets_structure():
    dc = _fit_small_dc()
    ens = EnsembleModel(dc=dc, elo=EloModel(), weight=0.5)
    out = ens.predict_markets("A", "B", neutral=True, elo_home=1700, elo_away=1500)
    assert sum(out["1x2"].values()) == pytest.approx(1.0)
    assert "over_under" in out and "btts" in out and "correct_score" in out
    assert "components" in out and "weight" in out["components"]


def _synthetic_results():
    # 4 equipos, fuerza A>B>C>D, a lo largo de 2019-2024 (incluye holdout reciente).
    strengths = {"A": 2.4, "B": 2.0, "C": 1.6, "D": 1.2}
    teams = list(strengths)
    rows = []
    day = date(2019, 1, 1)
    from datetime import timedelta
    i = 0
    while day < date(2024, 6, 1):
        h = teams[i % 4]
        a = teams[(i + 1 + (i // 4)) % 4]
        if h == a:
            a = teams[(i + 2) % 4]
        # marcador determinista según fuerza
        hg = int(strengths[h]); ag = int(strengths[a])
        rows.append((day, h, a, hg, ag, True))
        day += timedelta(days=7)
        i += 1
    return rows


def test_train_produces_valid_model(tmp_path):
    results = _synthetic_results()
    model = train(results, train_years=6, holdout_days=365, min_team_matches=3)
    assert 0.0 <= model.weight <= 1.0
    assert model.xi in (0.0, 0.0019)
    assert "rps_ensemble" in model.metrics
    # Serialización y persistencia.
    restored = EnsembleModel.from_dict(model.to_dict())
    p = model.save(str(tmp_path / "m.json"))
    assert p.exists()
    loaded = EnsembleModel.load(str(tmp_path / "m.json"))
    assert loaded.weight == model.weight
    # Predicción reproducible tras roundtrip.
    a = restored.predict_1x2("A", "B", True, None, 1700, 1500)
    b = model.predict_1x2("A", "B", True, None, 1700, 1500)
    assert a["home"] == pytest.approx(b["home"])
