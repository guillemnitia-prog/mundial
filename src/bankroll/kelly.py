"""Dimensionamiento del stake: ¼ Kelly sobre el saldo individual (SPEC §5.1).

La FRACCIÓN recomendada (¼ Kelly con tope 5%) es independiente del usuario y se guarda en
`predictions.recommended_stake`. El importe en € es POR USUARIO sobre su saldo actual, con halving
si el saldo cayó >50% y con el mínimo de la casa ("demasiado pequeña, no apostar").
"""

from __future__ import annotations

from src.config import settings
from src.db.schema import Prediction

INITIAL_BALANCE = 50.0  # saldo virtual de partida por usuario


def kelly_fraction(p: float, odds: float) -> float:
    """Fracción de Kelly completa: f = ((odds−1)·p − (1−p)) / (odds−1). 0 si no hay edge."""
    b = odds - 1.0
    if b <= 0:
        return 0.0
    f = (b * p - (1.0 - p)) / b
    return f if f > 0 else 0.0


def recommended_fraction(p: float, odds: float) -> float:
    """¼ Kelly con tope MAX_STAKE_PCT (user-independent). 0 si no hay edge."""
    f = kelly_fraction(p, odds) * settings.kelly_fraction
    return min(f, settings.max_stake_pct)


def user_stake(balance: float, fraction: float, initial_balance: float = INITIAL_BALANCE) -> dict:
    """Importe por usuario a partir de la fracción recomendada.

    Aplica halving si el saldo cayó por debajo del 50% del inicial (no perseguir pérdidas).
    Devuelve {fraction, eur, pct, too_small, bettable, message}.
    """
    eff_fraction = fraction
    halved = False
    if balance < 0.5 * initial_balance:
        eff_fraction = fraction / 2.0
        halved = True

    eur = round(balance * eff_fraction, 2)
    pct = eff_fraction
    too_small = eur < settings.min_stake_eur
    bettable = eff_fraction > 0 and not too_small
    message = "demasiado pequeña, no apostar" if (eff_fraction > 0 and too_small) else None
    return {
        "fraction": eff_fraction,
        "eur": eur,
        "pct": pct,
        "too_small": too_small,
        "bettable": bettable,
        "halved": halved,
        "message": message,
    }


def compute(p: float, odds: float, balance: float, initial_balance: float = INITIAL_BALANCE) -> dict:
    """Atajo: de (prob, cuota, saldo) al detalle de stake para la UI."""
    frac = recommended_fraction(p, odds)
    return user_stake(balance, frac, initial_balance)


def assign_recommended_stake(prediction: Prediction) -> float:
    """Setea y devuelve la fracción ¼ Kelly recomendada en la predicción (user-independent)."""
    frac = recommended_fraction(prediction.model_prob, prediction.offered_odds)
    prediction.recommended_stake = frac
    return frac
