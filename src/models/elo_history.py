"""Reconstrucción del Elo histórico (replay).

eloratings.net solo da el Elo ACTUAL. Para calibrar la tasa de empate por |dr| y para evaluar el
componente Elo en el pasado necesitamos el Elo PRE-PARTIDO de cada partido histórico, así que lo
reconstruimos replayando los resultados con un actualizador Elo estándar (K-factor + ventaja local).

No replica exactamente la fórmula de eloratings.net (que pondera por margen y tipo de torneo), pero
es una aproximación honesta y suficiente para calibrar empates y para el backtest del blend.
"""

from __future__ import annotations

from src.models.elo_model import HOST_ELO_BONUS

DEFAULT_K = 20.0
BASE_RATING = 1500.0


def _expected(dr: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-dr / 400.0))


def replay_elo(matches, k: float = DEFAULT_K, home_adv: float = HOST_ELO_BONUS,
               base: float = BASE_RATING) -> tuple[list[dict], dict[str, float]]:
    """Replaya partidos en orden temporal.

    `matches`: iterable de (date, home, away, home_goals, away_goals, neutral) ORDENADO por fecha.
    Devuelve (records, final_ratings) donde cada record incluye el Elo pre-partido de ambos, el dr
    (con ventaja local si no es neutral) y si fue empate.
    """
    ratings: dict[str, float] = {}
    records: list[dict] = []

    for (d, home, away, hg, ag, neutral) in matches:
        rh = ratings.get(home, base)
        ra = ratings.get(away, base)
        dr = rh - ra + (0.0 if neutral else home_adv)

        we = _expected(dr)
        if hg > ag:
            score_h = 1.0
        elif hg < ag:
            score_h = 0.0
        else:
            score_h = 0.5

        records.append({
            "date": d, "home": home, "away": away,
            "pre_home": rh, "pre_away": ra, "dr": dr,
            "is_draw": hg == ag, "neutral": neutral,
            "home_goals": hg, "away_goals": ag,
        })

        delta = k * (score_h - we)
        ratings[home] = rh + delta
        ratings[away] = ra - delta

    return records, ratings


def draw_samples(records) -> list[tuple[float, bool]]:
    """Extrae (dr, is_draw) de los records para calibrar EloModel.fit_draw_rates."""
    return [(r["dr"], r["is_draw"]) for r in records]
