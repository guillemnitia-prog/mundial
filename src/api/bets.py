"""Endpoints de decisión de apuesta e historial del usuario (SPEC §5.3, §7)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import require_onboarded
from src.bankroll.bets import BettingError, record_decision
from src.db.schema import Bet, Prediction, User
from src.db.session import get_db

router = APIRouter(tags=["bets"])

# Códigos de dominio → códigos HTTP.
_ERROR_STATUS = {
    "betting_locked": status.HTTP_409_CONFLICT,
    "invalid_amount": 422,  # Unprocessable Content
    "invalid_action": status.HTTP_400_BAD_REQUEST,
    "match_not_found": status.HTTP_404_NOT_FOUND,
}


class DecisionRequest(BaseModel):
    action: str  # accept | reject | modify
    amount: float | None = None  # solo para 'modify'


class BetOut(BaseModel):
    id: int
    match_id: int
    prediction_id: int | None
    market: str
    outcome: str
    stake: float
    odds: float
    decision: str
    recommended_stake: float | None
    status: str
    pnl: float | None

    @classmethod
    def from_bet(cls, b: Bet) -> "BetOut":
        return cls(
            id=b.id, match_id=b.match_id, prediction_id=b.prediction_id,
            market=b.market, outcome=b.outcome, stake=b.stake, odds=b.odds,
            decision=b.decision, recommended_stake=b.recommended_stake,
            status=b.status, pnl=b.pnl,
        )


@router.post("/predictions/{prediction_id}/decision", response_model=BetOut)
def decide(
    prediction_id: int,
    payload: DecisionRequest,
    current_user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> BetOut:
    prediction = db.get(Prediction, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="prediction_not_found")
    try:
        bet = record_decision(db, current_user, prediction, payload.action, payload.amount)
    except BettingError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.code,
        )
    return BetOut.from_bet(bet)


@router.get("/me/bets", response_model=list[BetOut])
def my_bets(
    current_user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> list[BetOut]:
    rows = db.execute(
        select(Bet).where(Bet.user_id == current_user.id).order_by(Bet.placed_at.desc())
    ).scalars().all()
    return [BetOut.from_bet(b) for b in rows]
