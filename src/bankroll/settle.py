"""Liquidación de apuestas con importe EFECTIVO por usuario (SPEC §5.2, §5.3).

Cada usuario puede tener un importe distinto en la misma apuesta, así que el beneficio/pérdida se
calcula individualmente. Liquidación neta:
    gana  → balance += stake·(cuota−1)
    pierde→ balance -= stake
Cada movimiento se registra en `balance_ledger`. Idempotente: no re-liquida apuestas ya cerradas.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.schema import BalanceLedger, Bet, Match, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_total_line(outcome: str) -> float:
    # "over_2.5" / "under_2.5" → 2.5
    return float(outcome.split("_", 1)[1])


def bet_won(market: str, outcome: str, home_goals: int, away_goals: int) -> bool:
    """Resuelve si una apuesta es ganadora dado el marcado final.

    Mercados soportados: 1X2 (home|draw|away), Over/Under (over_X|under_X), BTTS (yes|no),
    marcador exacto ("h-a"). Caveat: usa el marcador almacenado (FT); el ajuste 90'/prórroga en
    eliminatorias se refina en Fase 12/ingest.
    """
    total = home_goals + away_goals
    if market == "1x2":
        if outcome == "home":
            return home_goals > away_goals
        if outcome == "away":
            return away_goals > home_goals
        if outcome == "draw":
            return home_goals == away_goals
        return False
    if market == "over_under":
        line = _parse_total_line(outcome)
        if outcome.startswith("over"):
            return total > line
        if outcome.startswith("under"):
            return total < line
        return False
    if market == "btts":
        both = home_goals >= 1 and away_goals >= 1
        return both if outcome == "yes" else (not both)
    if market == "correct_score":
        try:
            h, a = (int(x) for x in outcome.split("-"))
        except ValueError:
            return False
        return home_goals == h and away_goals == a
    return False


def settle_bet(db: Session, bet: Bet, home_goals: int, away_goals: int) -> None:
    """Liquida una apuesta abierta con su importe efectivo y registra el movimiento."""
    if bet.status != "open" or bet.decision == "rejected":
        return  # ya liquidada, anulada o rechazada → fuera

    user = db.get(User, bet.user_id)
    won = bet_won(bet.market, bet.outcome, home_goals, away_goals)
    if won:
        delta = bet.stake * (bet.odds - 1.0)
        bet.status, bet.result = "won", "won"
    else:
        delta = -bet.stake
        bet.status, bet.result = "lost", "lost"

    bet.pnl = round(delta, 2)
    bet.settled_at = _utcnow()
    user.balance = round(user.balance + delta, 2)

    db.add(
        BalanceLedger(
            user_id=user.id,
            bet_id=bet.id,
            delta=round(delta, 2),
            balance_after=user.balance,
        )
    )


def settle_match(db: Session, match: Match) -> dict:
    """Liquida todas las apuestas abiertas de un partido finalizado con marcador.

    Devuelve un resumen {settled, won, lost}. Idempotente.
    """
    if match.home_goals is None or match.away_goals is None:
        raise ValueError("El partido no tiene marcador para liquidar.")

    bets = db.execute(
        select(Bet).where(Bet.match_id == match.id, Bet.status == "open")
    ).scalars().all()

    summary = {"settled": 0, "won": 0, "lost": 0}
    for bet in bets:
        if bet.decision == "rejected":
            continue
        settle_bet(db, bet, match.home_goals, match.away_goals)
        summary["settled"] += 1
        summary[bet.status] += 1
    db.commit()
    return summary
