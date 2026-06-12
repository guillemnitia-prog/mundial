"""Métricas de calibración para 1X2 (SPEC §3.4): RPS y Brier.

Resultado ordinal con 3 categorías: home, draw, away. El RPS (Ranked Probability Score) respeta
ese orden; el Brier es la versión multiclase. Ambas: menor = mejor; predicción perfecta = 0.
"""

from __future__ import annotations

OUTCOMES = ("home", "draw", "away")


def _probs_vector(probs: dict) -> list[float]:
    return [probs.get(k, 0.0) for k in OUTCOMES]


def rps(probs: dict, outcome: str) -> float:
    """Ranked Probability Score para 1X2 (ordinal home<draw<away).

    RPS = (1/(r−1)) · Σ_{i=1}^{r−1} (CP_i − CO_i)^2, con r=3 categorías.
    """
    p = _probs_vector(probs)
    o = [1.0 if k == outcome else 0.0 for k in OUTCOMES]
    cum_p = cum_o = 0.0
    total = 0.0
    for i in range(len(OUTCOMES) - 1):  # i = 0,1
        cum_p += p[i]
        cum_o += o[i]
        total += (cum_p - cum_o) ** 2
    return total / (len(OUTCOMES) - 1)


def brier(probs: dict, outcome: str) -> float:
    """Brier multiclase: Σ (p_i − o_i)^2 sobre las 3 categorías."""
    p = _probs_vector(probs)
    o = [1.0 if k == outcome else 0.0 for k in OUTCOMES]
    return sum((pi - oi) ** 2 for pi, oi in zip(p, o))


def mean_rps(predictions, outcomes) -> float:
    preds = list(predictions)
    outs = list(outcomes)
    if not preds:
        return float("nan")
    return sum(rps(p, o) for p, o in zip(preds, outs)) / len(preds)


def mean_brier(predictions, outcomes) -> float:
    preds = list(predictions)
    outs = list(outcomes)
    if not preds:
        return float("nan")
    return sum(brier(p, o) for p, o in zip(preds, outs)) / len(preds)


def result_outcome(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home"
    if home_goals < away_goals:
        return "away"
    return "draw"
