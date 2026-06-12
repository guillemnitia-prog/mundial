"""Decisión de apuesta por usuario sobre una recomendación (SPEC §5.3).

Cada usuario puede, sobre una recomendación (`predictions`): aceptar (importe recomendado),
rechazar (no apuesta), cambiar importe (acepta con su propio importe) o no interactuar
(= apostar lo recomendado por defecto). El importe EFECTIVO por usuario manda en la liquidación.
La decisión es editable hasta que el partido empieza; al pasar a estado distinto de "scheduled"
queda bloqueada.

La liquidación es neta: el stake no se descuenta al apostar, solo al liquidar (ver settle.py).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.bankroll import kelly
from src.config import settings
from src.db.schema import Bet, Match, Prediction, User


class BettingError(Exception):
    """Error de dominio al registrar una decisión (code legible para la API/UI)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def recommended_eur(user: User, prediction: Prediction) -> float:
    """Importe recomendado en € para este usuario (¼ Kelly sobre su saldo, con halving).

    `prediction.recommended_stake` es la fracción del saldo (¼ Kelly con tope 5%, la rellena
    bankroll/kelly.py). El € se calcula por usuario sobre su saldo actual. Si es None → 0.
    """
    frac = prediction.recommended_stake or 0.0
    return kelly.user_stake(user.balance, frac)["eur"]


def _get_bet(db: Session, user_id: int, prediction_id: int) -> Bet | None:
    return db.execute(
        select(Bet).where(Bet.user_id == user_id, Bet.prediction_id == prediction_id)
    ).scalar_one_or_none()


def record_decision(
    db: Session,
    user: User,
    prediction: Prediction,
    action: str,
    custom_amount: float | None = None,
) -> Bet:
    """Registra/actualiza la decisión del usuario sobre una recomendación.

    action: "accept" | "reject" | "modify". Devuelve la fila `Bet`. Lanza BettingError con un
    código (`betting_locked`, `invalid_action`, `invalid_amount`).
    """
    match = db.get(Match, prediction.match_id)
    if match is None:
        raise BettingError("match_not_found")
    # Bloqueo al empezar el partido: solo editable mientras está programado.
    if match.status != "scheduled":
        raise BettingError("betting_locked")

    rec = recommended_eur(user, prediction)

    if action == "accept":
        decision, stake, status = "recommended", rec, "open"
    elif action == "reject":
        decision, stake, status = "rejected", 0.0, "void"
    elif action == "modify":
        if custom_amount is None:
            raise BettingError("invalid_amount")
        amount = round(float(custom_amount), 2)
        # Validar: mínimo de la casa ≤ importe ≤ saldo actual.
        if amount < settings.min_stake_eur or amount > user.balance:
            raise BettingError("invalid_amount")
        decision, stake, status = "modified", amount, "open"
    else:
        raise BettingError("invalid_action")

    bet = _get_bet(db, user.id, prediction.id)
    if bet is None:
        bet = Bet(
            user_id=user.id,
            match_id=match.id,
            prediction_id=prediction.id,
            market=prediction.market,
            outcome=prediction.outcome,
            odds=prediction.offered_odds,
        )
        db.add(bet)
    bet.decision = decision
    bet.stake = stake
    bet.recommended_stake = rec
    bet.status = status
    # Re-decidir reabre una apuesta previamente anulada/abierta (mientras esté programado).
    bet.result = None
    bet.pnl = None
    bet.settled_at = None
    db.commit()
    return bet


def materialize_default_bets(
    db: Session,
    prediction: Prediction,
    recommended_by_user: dict[int, float] | None = None,
) -> int:
    """Crea apuestas por defecto (decision='default') para los usuarios que NO interactuaron.

    Se invoca al bloquearse el partido (kickoff). Los que rechazaron tienen fila 'rejected' y
    quedan fuera; los que aceptaron/modificaron ya tienen fila. `recommended_by_user` permite
    pasar importes precalculados (Kelly); si falta, se calcula con `recommended_eur`.
    """
    recommended_by_user = recommended_by_user or {}
    decided_user_ids = {
        uid for (uid,) in db.execute(
            select(Bet.user_id).where(Bet.prediction_id == prediction.id)
        ).all()
    }
    match = db.get(Match, prediction.match_id)
    created = 0
    for user in db.execute(select(User)).scalars().all():
        if user.id in decided_user_ids:
            continue
        stake = recommended_by_user.get(user.id)
        if stake is None:
            stake = recommended_eur(user, prediction)
        db.add(
            Bet(
                user_id=user.id,
                match_id=match.id,
                prediction_id=prediction.id,
                market=prediction.market,
                outcome=prediction.outcome,
                odds=prediction.offered_odds,
                decision="default",
                stake=stake,
                recommended_stake=stake,
                status="open",
            )
        )
        created += 1
    db.commit()
    return created
