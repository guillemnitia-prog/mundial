"""Ensemble Dixon-Coles + Elo (SPEC §3.3, §3.4).

- El 1X2 final es media ponderada: `w·DC + (1−w)·Elo` (renormalizado).
- Over/Under, BTTS y marcador exacto se derivan de la matriz de marcadores de DC (Elo no opina).
- `train()` ajusta DC sobre una ventana reciente, reconstruye el Elo histórico para calibrar la
  tasa de empate, y elige `(w, ξ)` por RPS en un holdout temporal. `backtest()` compara ensemble
  vs DC-solo vs Elo-solo. El artefacto entrenado se serializa a `data/model_params.json`.

Comparación con el cierre de mercado (SPEC §3.4): no hay histórico de cuotas fiable (decidido en
Fase 0), así que el backtest mide RPS/Brier absolutos y frente a los componentes; la comparación
con el cierre queda pendiente y se reporta explícitamente.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from src.config import BASE_DIR, settings
from src.models.dixon_coles import DixonColesModel
from src.models.elo_history import draw_samples, replay_elo
from src.models.elo_model import EloModel
from src.models.metrics import mean_brier, mean_rps, result_outcome

WEIGHT_GRID = [i / 10 for i in range(11)]   # 0.0 .. 1.0
XI_GRID = [0.0, 0.0019]                       # 0 y ~vida media 1 año (1/día)


def _host_side(neutral: bool) -> str | None:
    """En el histórico, la ventaja local va al equipo de casa si el partido no es neutral."""
    return None if neutral else "home"


def _to_dc_row(r: tuple) -> tuple:
    """(date, home, away, hg, ag, neutral) → (home, away, hg, ag, date, neutral) para DixonColes."""
    d, home, away, hg, ag, neutral = r
    return (home, away, hg, ag, d, neutral)


@dataclass
class EnsembleModel:
    dc: DixonColesModel
    elo: EloModel
    weight: float = 0.5      # peso del DC en el 1X2
    xi: float = 0.0
    metrics: dict = field(default_factory=dict)

    def predict_1x2(self, home, away, neutral, host_side, elo_home, elo_away) -> dict:
        dc_1x2 = self.dc.predict_markets(home, away, neutral, host_side)["1x2"]
        elo_side = host_side if not neutral else None
        elo_1x2 = self.elo.predict_1x2(elo_home, elo_away, elo_side)
        w = self.weight
        blended = {k: w * dc_1x2[k] + (1 - w) * elo_1x2[k] for k in ("home", "draw", "away")}
        total = sum(blended.values()) or 1.0
        return {k: v / total for k, v in blended.items()}

    def predict_markets(self, home, away, neutral=True, host_side=None,
                        elo_home=1500.0, elo_away=1500.0) -> dict:
        markets = self.dc.predict_markets(home, away, neutral, host_side)
        dc_1x2 = markets["1x2"]
        blended = self.predict_1x2(home, away, neutral, host_side, elo_home, elo_away)
        markets["1x2"] = blended
        markets["components"] = {
            "dc_1x2": dc_1x2,
            "elo_1x2": self.elo.predict_1x2(
                elo_home, elo_away, host_side if not neutral else None
            ),
            "weight": self.weight,
        }
        return markets

    # --- serialización ----------------------------------------------------

    def to_dict(self) -> dict:
        return {"dc": self.dc.to_dict(), "elo": self.elo.to_dict(),
                "weight": self.weight, "xi": self.xi, "metrics": self.metrics}

    @classmethod
    def from_dict(cls, d: dict) -> "EnsembleModel":
        return cls(
            dc=DixonColesModel.from_dict(d["dc"]),
            elo=EloModel.from_dict(d["elo"]),
            weight=float(d.get("weight", 0.5)),
            xi=float(d.get("xi", 0.0)),
            metrics=dict(d.get("metrics", {})),
        )

    def save(self, path: str | None = None) -> Path:
        p = Path(path or settings.model_params_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict()), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | None = None) -> "EnsembleModel":
        p = Path(path or settings.model_params_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))


# --- entrenamiento / backtest ---------------------------------------------

def _eligible(records, dc: DixonColesModel):
    """Records de test con ambos equipos conocidos por el DC."""
    known = set(dc.attack)
    return [r for r in records if r["home"] in known and r["away"] in known]


def _fit_dc(results, xi, as_of, train_years, min_team_matches):
    """Ajusta DC sobre la ventana [as_of−train_years, as_of), filtrando equipos con pocos partidos."""
    start = as_of - timedelta(days=365 * train_years)
    window = [r for r in results if start <= r[0] < as_of]
    # Filtrar equipos con muy pocos partidos (estabilidad y velocidad).
    counts: dict[str, int] = {}
    for _, h, a, *_ in window:
        counts[h] = counts.get(h, 0) + 1
        counts[a] = counts.get(a, 0) + 1
    rows = [r for r in window
            if counts.get(r[1], 0) >= min_team_matches and counts.get(r[2], 0) >= min_team_matches]
    dc = DixonColesModel().fit((_to_dc_row(r) for r in rows), xi=xi, as_of=as_of)
    return dc


def train(results, as_of: date | None = None, train_years: int | None = None,
          holdout_days: int = 730, min_team_matches: int = 20,
          weight_grid=WEIGHT_GRID, xi_grid=XI_GRID) -> EnsembleModel:
    """Entrena el ensemble: ajusta DC, calibra Elo y elige (w, ξ) por RPS en el holdout."""
    results = sorted(results, key=lambda r: r[0])
    if not results:
        raise ValueError("Sin resultados para entrenar.")
    as_of = as_of or (results[-1][0] + timedelta(days=1))
    train_years = train_years or settings.dc_train_years

    # Elo histórico (todos los partidos) → calibración de empates + Elo pre-partido.
    records, _final = replay_elo(results)
    elo = EloModel().fit_draw_rates(draw_samples(records))
    rec_by_key = {(r["date"], r["home"], r["away"]): r for r in records}

    holdout_start = as_of - timedelta(days=holdout_days)
    test_rows = [r for r in results if holdout_start <= r[0] < as_of]

    best = None  # (rps, weight, xi)
    for xi in xi_grid:
        dc = _fit_dc(results, xi, holdout_start, train_years, min_team_matches)
        # Predicciones de test elegibles.
        known = set(dc.attack)
        evals = []  # (dc_1x2, elo_1x2, outcome)
        for r in test_rows:
            d, home, away, hg, ag, neutral = r
            if home not in known or away not in known:
                continue
            rec = rec_by_key.get((d, home, away))
            if rec is None:
                continue
            hs = _host_side(neutral)
            dc_1x2 = dc.predict_markets(home, away, neutral, hs)["1x2"]
            elo_1x2 = elo.predict_1x2(rec["pre_home"], rec["pre_away"], hs)
            evals.append((dc_1x2, elo_1x2, result_outcome(hg, ag)))
        if not evals:
            continue
        for w in weight_grid:
            preds = [
                {k: w * dc1[k] + (1 - w) * el[k] for k in ("home", "draw", "away")}
                for (dc1, el, _) in evals
            ]
            score = mean_rps(preds, [o for *_, o in evals])
            if best is None or score < best[0]:
                best = (score, w, xi)

    if best is None:
        best = (float("nan"), 0.5, 0.0)
    _, weight, xi = best

    # Backtest honesto con el DC del holdout (sin fuga) y métricas por componente.
    metrics = backtest(results, weight, xi, as_of=holdout_start, train_years=train_years,
                       holdout_days=holdout_days, min_team_matches=min_team_matches, elo=elo,
                       records_by_key=rec_by_key)

    # Modelo final: refit DC con TODOS los datos hasta as_of (despliegue).
    dc_final = _fit_dc(results, xi, as_of, train_years, min_team_matches)
    return EnsembleModel(dc=dc_final, elo=elo, weight=weight, xi=xi, metrics=metrics)


def backtest(results, weight, xi, as_of, train_years, holdout_days, min_team_matches,
             elo: EloModel | None = None, records_by_key: dict | None = None) -> dict:
    """RPS/Brier de ensemble vs DC-solo vs Elo-solo en el holdout (modelos sin ver el test)."""
    results = sorted(results, key=lambda r: r[0])
    if elo is None or records_by_key is None:
        records, _ = replay_elo(results)
        elo = EloModel().fit_draw_rates(draw_samples(records))
        records_by_key = {(r["date"], r["home"], r["away"]): r for r in records}

    dc = _fit_dc(results, xi, as_of, train_years, min_team_matches)
    known = set(dc.attack)
    holdout_start, holdout_end = as_of, as_of + timedelta(days=holdout_days)

    ens_preds, dc_preds, elo_preds, outs = [], [], [], []
    for r in results:
        d, home, away, hg, ag, neutral = r
        if not (holdout_start <= d < holdout_end):
            continue
        if home not in known or away not in known:
            continue
        rec = records_by_key.get((d, home, away))
        if rec is None:
            continue
        hs = _host_side(neutral)
        dc_1x2 = dc.predict_markets(home, away, neutral, hs)["1x2"]
        elo_1x2 = elo.predict_1x2(rec["pre_home"], rec["pre_away"], hs)
        ens = {k: weight * dc_1x2[k] + (1 - weight) * elo_1x2[k] for k in ("home", "draw", "away")}
        ens_preds.append(ens); dc_preds.append(dc_1x2); elo_preds.append(elo_1x2)
        outs.append(result_outcome(hg, ag))

    return {
        "n": len(outs),
        "rps_ensemble": mean_rps(ens_preds, outs),
        "rps_dc": mean_rps(dc_preds, outs),
        "rps_elo": mean_rps(elo_preds, outs),
        "brier_ensemble": mean_brier(ens_preds, outs),
        "closing_odds_comparison": "pendiente (sin histórico de cuotas, ver SPEC §3.4)",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Entrenar el ensemble DC+Elo.")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--train-years", type=int, default=None)
    parser.add_argument("--min-team-matches", type=int, default=20)
    args = parser.parse_args(argv)

    from src.db.session import SessionLocal, init_db
    from src.ingest.historical import load_results

    init_db()
    with SessionLocal() as db:
        results = load_results(db)
    print(f"Histórico: {len(results)} partidos con marcador.")
    model = train(results, train_years=args.train_years, min_team_matches=args.min_team_matches)
    path = model.save()
    m = model.metrics
    print(f"weight (DC)={model.weight:.2f}  xi={model.xi}")
    print(f"backtest n={m.get('n')}  RPS ensemble={m.get('rps_ensemble'):.4f}  "
          f"DC={m.get('rps_dc'):.4f}  Elo={m.get('rps_elo'):.4f}")
    print(f"Comparación cierre: {m.get('closing_odds_comparison')}")
    print(f"Artefacto guardado en: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
