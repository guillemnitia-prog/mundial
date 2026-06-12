"""Construcción de payloads de notificación (SPEC §10.2).

Las plantillas EXACTAS de contenido viven aquí. El envío real por Web Push (pywebpush) se cablea
en la Fase 13; por ahora `dispatch` registra los payloads (stub testeable).
"""

from __future__ import annotations

import logging

from src.db.schema import Bet, Match, Team, User

logger = logging.getLogger("notifications")


def _eur(n: float) -> str:
    return f"{n:.2f} €".replace(".", ",")


def _odds(n: float) -> str:
    return f"{n:.2f}"


def _teams(db, match: Match) -> tuple[str, str]:
    home = db.get(Team, match.home_id) if match.home_id else None
    away = db.get(Team, match.away_id) if match.away_id else None
    return (home.name if home else "Local", away.name if away else "Visitante")


def settlement_message(db, user: User, bet: Bet, match: Match) -> dict:
    """Payload tras liquidar (SPEC §10.2: ganó / perdió)."""
    home, away = _teams(db, match)
    if bet.status == "won":
        profit = bet.stake * (bet.odds - 1.0)
        title = f"🟢 ¡Apuesta ganada! {home} vs {away}"
        body = (f"Apostaste {_eur(bet.stake)} a {bet.outcome} @{_odds(bet.odds)} → +{_eur(profit)}\n"
                f"Saldo actual: {_eur(user.balance)}")
    else:
        title = f"🔴 Apuesta perdida — {home} vs {away}"
        body = (f"Apostaste {_eur(bet.stake)} a {bet.outcome} @{_odds(bet.odds)} → -{_eur(bet.stake)}\n"
                f"Saldo actual: {_eur(user.balance)}")
    return {"user_id": user.id, "title": title, "body": body, "url": f"/matches/{match.id}"}


def pre_match_message(db, match: Match, outcome: str, odds: float, stake_eur: float) -> dict:
    """Payload 1 hora antes con la apuesta recomendada (SPEC §10.2)."""
    home, away = _teams(db, match)
    title = f"⚽ En 1 hora: {home} vs {away}"
    body = f"Apuesta recomendada: {outcome} @{_odds(odds)} — stake sugerido: {_eur(stake_eur)}"
    return {"title": title, "body": body, "url": f"/matches/{match.id}"}


def dispatch(payloads: list[dict]) -> int:
    """Stub de envío: registra los payloads. La Fase 13 lo conecta a pywebpush. Devuelve nº enviados."""
    for p in payloads:
        logger.info("PUSH (stub): %s — %s", p.get("title"), p.get("body"))
    return len(payloads)
