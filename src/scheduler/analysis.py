"""Orquestación del análisis de un partido (SPEC §3.3, §4, §11).

Combina ensemble (Dixon-Coles + Elo) + odds (devig consenso eu) + value (doble filtro) + kelly
para escribir las `predictions` de un partido y marcarlo como analizado. Es el cableado del modelo
con los datos reales. Sin odds (p.ej. sin ODDS_API_KEY) → 0 picks ("Sin apuesta de valor").
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.bankroll import kelly
from src.db.schema import Bet, Match, Odds, Prediction, Team
from src.models.ensemble import EnsembleModel
from src.value import ev as ev_mod
from src.value.devig import remove_margin

# Alias para desajustes de nombres football-data ↔ martj42 (datos de entrenamiento de DC).
TEAM_NAME_ALIASES = {
    "Congo DR": "DR Congo",
    "Cape Verde Islands": "Cape Verde",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Czechia": "Czech Republic",
}


def _model_name(team: Team, ensemble: EnsembleModel) -> str | None:
    """Nombre del equipo tal como lo conoce el DC (con alias). None si no está."""
    for candidate in (team.name, TEAM_NAME_ALIASES.get(team.name)):
        if candidate and candidate in ensemble.dc.attack:
            return candidate
    return None


def _consensus_market_odds(db: Session, match_id: int) -> dict[str, dict[str, dict]]:
    """Agrupa odds por (market, outcome): mejor cuota ofrecida + fair_prob por consenso/devig.

    Devuelve {market: {outcome: {"odds": mejor_cuota, "fair_prob": prob_justa}}}.
    """
    rows = db.execute(select(Odds).where(Odds.match_id == match_id)).scalars().all()
    # Implícitas por (market, outcome) promediadas entre bookmakers; mejor cuota = máx.
    by_market: dict[str, dict[str, list[float]]] = {}
    best_odds: dict[str, dict[str, float]] = {}
    for o in rows:
        by_market.setdefault(o.market, {}).setdefault(o.outcome, []).append(o.price)
        best_odds.setdefault(o.market, {})
        best_odds[o.market][o.outcome] = max(best_odds[o.market].get(o.outcome, 0.0), o.price)

    out: dict[str, dict[str, dict]] = {}
    for market, outcomes in by_market.items():
        implied = {oc: sum(1.0 / p for p in prices) / len(prices) for oc, prices in outcomes.items()}
        # Devig POR GRUPO de mercado de 2 vías: en Over/Under y hándicap hay que normalizar cada
        # línea por separado (over_2.5 vs under_2.5), no todas las líneas juntas.
        groups: dict[str, dict[str, float]] = {}
        for oc, imp in implied.items():
            groups.setdefault(_devig_group(market, oc), {})[oc] = imp
        fair: dict[str, float] = {}
        for grp in groups.values():
            fair_grp, _ = remove_margin(grp)
            fair.update(fair_grp)
        out[market] = {
            oc: {"odds": best_odds[market][oc], "fair_prob": fair[oc]} for oc in outcomes
        }
    return out


def _devig_group(market: str, outcome: str) -> str:
    """Clave de agrupación para quitar el margen. Over/Under y hándicap se normalizan por LÍNEA."""
    if market in ("over_under", "asian_handicap"):
        # outcome tipo 'over_2.5' / 'under_2.5' / 'home_-0.5' → agrupar por la línea (número).
        parts = outcome.rsplit("_", 1)
        return f"{market}:{parts[1]}" if len(parts) == 2 else market
    return market


def _model_markets(match: Match, home: Team, away: Team, ensemble: EnsembleModel) -> dict | None:
    """Probabilidades del modelo por mercado. Usa ensemble si ambos equipos están en DC; si no,
    fallback Elo-solo (solo 1X2). None si no hay datos suficientes."""
    host_side = None
    if not match.neutral_venue:
        host_side = "home" if home.is_host else ("away" if away.is_host else "home")

    hn, an = _model_name(home, ensemble), _model_name(away, ensemble)
    if hn and an:
        elo_h = home.elo if home.elo is not None else 1500.0
        elo_a = away.elo if away.elo is not None else 1500.0
        return ensemble.predict_markets(hn, an, match.neutral_venue, host_side, elo_h, elo_a)

    # Fallback Elo-solo (necesita Elo de ambos).
    if home.elo is not None and away.elo is not None:
        elo_side = host_side if not match.neutral_venue else None
        return {"1x2": ensemble.elo.predict_1x2(home.elo, away.elo, elo_side)}
    return None


def _upsert_predictions(db: Session, match_id: int, picks: list[dict]) -> None:
    """Upsert por (market, outcome): preserva ids/enlaces de bets; borra los no-pick sin bet."""
    existing = {
        (p.market, p.outcome): p
        for p in db.execute(select(Prediction).where(Prediction.match_id == match_id)).scalars()
    }
    keep_keys = {(p["market"], p["outcome"]) for p in picks}

    for rank, pk in enumerate(picks, start=1):
        key = (pk["market"], pk["outcome"])
        frac = kelly.recommended_fraction(pk["model_prob"], pk["offered_odds"])
        pred = existing.get(key)
        if pred is None:
            pred = Prediction(match_id=match_id, market=pk["market"], outcome=pk["outcome"])
            db.add(pred)
        pred.model_prob = pk["model_prob"]
        pred.fair_prob = pk["fair_prob"]
        pred.offered_odds = pk["offered_odds"]
        pred.ev = pk["ev"]
        pred.confidence = pk["confidence"]
        pred.recommended_stake = frac
        pred.rank = rank

    # Borrar predicciones que ya no son pick y no están referenciadas por una bet.
    referenced = {
        pid for (pid,) in db.execute(
            select(Bet.prediction_id).where(Bet.match_id == match_id, Bet.prediction_id.isnot(None))
        ).all()
    }
    for key, pred in existing.items():
        if key not in keep_keys:
            if pred.id in referenced:
                # Conserva la fila (enlace de bet) pero la saca de los picks actuales.
                pred.rank = None
            else:
                db.delete(pred)


def analyze_match(db: Session, match: Match, ensemble: EnsembleModel, stage: str = "preliminary",
                  now: datetime | None = None) -> list[dict]:
    """Analiza un partido: genera picks de valor, escribe predictions y marca analizado."""
    now = now or datetime.now(timezone.utc)
    home = db.get(Team, match.home_id) if match.home_id else None
    away = db.get(Team, match.away_id) if match.away_id else None

    picks: list[dict] = []
    model_markets = None
    if home is not None and away is not None:
        model_markets = _model_markets(match, home, away, ensemble)
        market_odds = _consensus_market_odds(db, match.id)
        if model_markets and market_odds:
            picks = ev_mod.select_value_bets(model_markets, market_odds)

    _upsert_predictions(db, match.id, picks)
    match.analysis_status = "analyzed"
    match.analysis_stage = stage
    match.analyzed_at = now
    match.analysis_json = _stats_summary(model_markets) if model_markets else None
    db.commit()
    return picks


def _stats_summary(model_markets: dict) -> str:
    """Resumen compacto del modelo para mostrar como 'estadísticas' en la UI."""
    out: dict = {}
    if "1x2" in model_markets:
        out["x1x2"] = {k: round(v, 3) for k, v in model_markets["1x2"].items()}
    if "over_under" in model_markets:
        ou = model_markets["over_under"]
        if "over_2.5" in ou:
            out["over25"] = round(ou["over_2.5"], 3)
    if "btts" in model_markets and "yes" in model_markets["btts"]:
        out["btts_yes"] = round(model_markets["btts"]["yes"], 3)
    return json.dumps(out)
