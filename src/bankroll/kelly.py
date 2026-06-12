"""Dimensionamiento del stake por usuario (SPEC §5.1).

Política (decidida por el usuario): cada apuesta = **max(20% del saldo, 10 €)**, con tope **25%**
del saldo. Si el saldo < 10 € no se recomienda apostar (importe demasiado pequeño). El stake es
POR USUARIO sobre su saldo ACTUAL: una misma recomendación da importes distintos a cada uno.

`predictions.recommended_stake` guarda la fracción nominal (MIN_STAKE_PCT = 0.20), user-independent;
el importe en € lo calcula `user_stake(balance)` aplicando suelo de 10 € y tope del 25%.
"""

from __future__ import annotations

from src.config import settings
from src.db.schema import Prediction


def kelly_fraction(p: float, odds: float) -> float:
    """Fracción de Kelly completa (informativa): f = ((odds−1)·p − (1−p)) / (odds−1). 0 si no hay edge."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - (1.0 - p)) / b
    return f if f > 0 else 0.0


def recommended_fraction(p: float, odds: float) -> float:
    """Fracción nominal recomendada (user-independent): el suelo de política (20%).

    El filtro de value (EV>0, confianza, cuota) lo aplica value/ev.py antes; aquí solo el sizing.
    """
    return settings.min_stake_pct


def user_stake(balance: float, fraction: float | None = None) -> dict:
    """Importe por usuario: max(20% del saldo, 10 €), limitado al 25% del saldo.

    En saldos bajos donde el mínimo de 10 € supera el 25%, manda el mínimo de 10 € (acotado al
    saldo). Saldo < 10 € → no apostar. Devuelve {eur, pct, too_small, bettable, message}.
    """
    min_eur = settings.min_stake_eur
    if balance < min_eur:
        return {"eur": 0.0, "pct": 0.0, "too_small": True, "bettable": False,
                "message": f"saldo insuficiente (mín. {min_eur:.0f} €)"}

    floor = max(settings.min_stake_pct * balance, min_eur)  # 20% del saldo o 10 €
    cap = settings.max_stake_pct * balance                  # 25% del saldo
    eur = floor if floor <= cap else min(floor, balance)    # en saldos bajos manda el mínimo de 10 €
    eur = round(eur, 2)
    pct = eur / balance if balance > 0 else 0.0
    return {"eur": eur, "pct": pct, "too_small": False, "bettable": True, "message": None}


def compute(p: float, odds: float, balance: float) -> dict:
    """Atajo para la UI: de (prob, cuota, saldo) al detalle de stake."""
    return user_stake(balance)


def assign_recommended_stake(prediction: Prediction) -> float:
    """Setea y devuelve la fracción nominal recomendada en la predicción (user-independent)."""
    frac = recommended_fraction(prediction.model_prob, prediction.offered_odds)
    prediction.recommended_stake = frac
    return frac
