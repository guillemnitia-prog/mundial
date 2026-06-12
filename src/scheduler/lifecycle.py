"""Transiciones de ciclo de vida y liquidación (SPEC §5, §11).

Tras ingerir resultados de football-data (que actualiza matches.status), este módulo:
- al pasar un partido a `live`: materializa las apuestas por defecto (lock) — quien no interactuó
  queda con la recomendación; quien rechazó queda fuera;
- al `finished` con goles: liquida con el importe efectivo de cada usuario (settle_match);
- recolecta los eventos de liquidación para disparar notificaciones (Fase 13).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.bankroll.bets import materialize_default_bets
from src.bankroll.settle import settle_match
from src.db.schema import Bet, Match, Prediction, User


def lock_live_matches(db: Session) -> int:
    """Para cada partido `live`, materializa los 'default' de sus predicciones. Idempotente."""
    matches = db.execute(select(Match).where(Match.status == "live")).scalars().all()
    created = 0
    for m in matches:
        preds = db.execute(select(Prediction).where(Prediction.match_id == m.id)).scalars().all()
        for p in preds:
            created += materialize_default_bets(db, p)
    return created


def settle_finished(db: Session) -> list[dict]:
    """Liquida los partidos finalizados con goles. Devuelve eventos {user, bet, match} para push."""
    matches = db.execute(
        select(Match).where(
            Match.status == "finished",
            Match.home_goals.isnot(None),
            Match.away_goals.isnot(None),
        )
    ).scalars().all()

    events: list[dict] = []
    for m in matches:
        # Apuestas que liquidaremos en esta pasada (estaban abiertas, no rechazadas).
        to_settle = db.execute(
            select(Bet).where(Bet.match_id == m.id, Bet.status == "open", Bet.decision != "rejected")
        ).scalars().all()
        if not to_settle:
            continue
        settle_match(db, m)
        for bet in to_settle:
            db.refresh(bet)
            user = db.get(User, bet.user_id)
            events.append({"user": user, "bet": bet, "match": m})
    return events


def transition_and_settle(db: Session) -> dict:
    """Lock de partidos en vivo + liquidación de finalizados. Devuelve resumen + eventos de push."""
    locked = lock_live_matches(db)
    events = settle_finished(db)
    return {"defaults_materialized": locked, "settlement_events": events}
