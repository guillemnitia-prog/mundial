"""Quitar el margen del bookie (devig) — SPEC §4.

La cuota implica una probabilidad con margen (overround). Para obtener la probabilidad "justa"
normalizamos proporcionalmente las implícitas del mercado. Usamos el CONSENSO de bookmakers eu
(promedio de implícitas) como mejor estimador, con aviso de que es proxy de Bet365.es/Sportium.
"""

from __future__ import annotations


def implied_prob(odds: float) -> float:
    """Probabilidad implícita = 1 / cuota_decimal."""
    if odds <= 0:
        raise ValueError("La cuota debe ser positiva.")
    return 1.0 / odds


def consensus_implied(odds_by_book: dict[str, dict[str, float]]) -> dict[str, float]:
    """Promedia las implícitas de varios bookmakers por outcome.

    `odds_by_book`: {bookmaker: {outcome: cuota}}. Devuelve {outcome: implícita_media}.
    Solo promedia los bookmakers que ofrecen ese outcome.
    """
    sums: dict[str, float] = {}
    counts: dict[str, int] = {}
    for book_odds in odds_by_book.values():
        for outcome, odds in book_odds.items():
            sums[outcome] = sums.get(outcome, 0.0) + implied_prob(odds)
            counts[outcome] = counts.get(outcome, 0) + 1
    return {o: sums[o] / counts[o] for o in sums}


def remove_margin(implied_by_outcome: dict[str, float]) -> tuple[dict[str, float], float]:
    """Normalización proporcional. Devuelve (fair_probs, overround).

    `implied_by_outcome`: {outcome: implícita} (de un mismo mercado). El overround es
    sum(implícitas) − 1. Las fair_probs suman 1.
    """
    total = sum(implied_by_outcome.values())
    if total <= 0:
        raise ValueError("Suma de implícitas no positiva.")
    fair = {o: p / total for o, p in implied_by_outcome.items()}
    return fair, total - 1.0


def fair_probs_from_odds(odds_by_book: dict[str, dict[str, float]]) -> tuple[dict, float]:
    """Atajo: consenso de implícitas + devig. Devuelve (fair_probs, overround)."""
    return remove_margin(consensus_implied(odds_by_book))
