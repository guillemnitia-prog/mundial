"""Selección de value bets — SPEC §4 (conservador y selectivo).

Doble filtro obligatorio: `model_prob ≥ MIN_CONFIDENCE` Y `EV>0`, con cuota ≥ MIN_ODDS.
Clasifica confianza (alta/media), devuelve HASTA 2 picks y NUNCA fuerza 2: si ninguno cumple,
lista vacía ("Sin apuesta de valor en este partido").
"""

from __future__ import annotations

from src.config import settings

# Umbrales de clasificación de confianza (sobre candidatos que YA pasaron el doble filtro).
CONF_PROB_ALTA = 0.75
CONF_EV_ALTA = 0.10


def ev(model_prob: float, odds: float) -> float:
    """EV por unidad apostada: model_prob·(odds−1) − (1−model_prob)."""
    return model_prob * (odds - 1.0) - (1.0 - model_prob)


def classify_confidence(model_prob: float, ev_value: float) -> str:
    """alta si prob y margen de EV son altos; media en otro caso."""
    if model_prob >= CONF_PROB_ALTA and ev_value >= CONF_EV_ALTA:
        return "alta"
    return "media"


def _iter_candidates(model_markets: dict, market_odds: dict):
    """Genera (market, outcome, model_prob, offered_odds, fair_prob) para outcomes con ambos datos.

    `model_markets`: {market: {outcome: model_prob}} (del ensemble; incluye 1x2, over_under, btts...).
    `market_odds`: {market: {outcome: {"odds": cuota, "fair_prob": prob_justa}}}.
    """
    for market, outcomes in market_odds.items():
        model_block = model_markets.get(market)
        if not isinstance(model_block, dict):
            continue
        for outcome, info in outcomes.items():
            if outcome not in model_block:
                continue
            yield (market, outcome, float(model_block[outcome]),
                   float(info["odds"]), float(info.get("fair_prob", 0.0)))


def select_value_bets(model_markets: dict, market_odds: dict, max_picks: int = 2) -> list[dict]:
    """Aplica el doble filtro y devuelve hasta `max_picks` recomendaciones (o lista vacía).

    Orden: confianza (alta>media) y luego EV descendente. No fuerza 2.
    """
    min_conf = settings.min_confidence
    min_odds = settings.min_odds

    candidates: list[dict] = []
    for market, outcome, model_prob, odds, fair_prob in _iter_candidates(model_markets, market_odds):
        if model_prob < min_conf:      # (a) alta confianza
            continue
        if odds < min_odds:            # cuota mínima
            continue
        ev_value = ev(model_prob, odds)
        if ev_value <= 0:              # (b) EV>0
            continue
        candidates.append({
            "market": market,
            "outcome": outcome,
            "model_prob": model_prob,
            "fair_prob": fair_prob,
            "offered_odds": odds,
            "ev": ev_value,
            "confidence": classify_confidence(model_prob, ev_value),
        })

    # Ordenar: alta antes que media, luego mayor EV.
    candidates.sort(key=lambda c: (0 if c["confidence"] == "alta" else 1, -c["ev"]))
    return candidates[:max_picks]
