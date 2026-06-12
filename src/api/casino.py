"""Endpoints del casino (ruleta con saldo virtual)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.auth.dependencies import require_onboarded
from src.casino import roulette
from src.db.schema import User
from src.db.session import get_db

router = APIRouter(prefix="/casino", tags=["casino"])


class RouletteBet(BaseModel):
    bet_type: str          # "color" | "number"
    selection: str | int   # "red"/"black"/"green" o 0..36
    amount: float


@router.post("/roulette")
def play_roulette(
    bet: RouletteBet,
    current_user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return roulette.spin(db, current_user, bet.bet_type, bet.selection, bet.amount)
    except roulette.RouletteError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.code)
