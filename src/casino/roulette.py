"""Ruleta europea (un solo 0) con saldo virtual. El resultado lo decide el SERVIDOR (justo).

Apuestas soportadas:
- color: 'red' | 'black'  → paga 1:1 (beneficio = importe)
- 'green' (el 0)          → paga 35:1
- número: 0..36           → paga 35:1

Liquidación neta sobre `users.balance`, registrada en `balance_ledger` (bet_id NULL).
"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from src.db.schema import BalanceLedger, User

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
MIN_BET = 1.0


class RouletteError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def color_of(n: int) -> str:
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


def _payout_multiplier(bet_type: str, selection, result: int) -> int:
    """Beneficio neto por unidad apostada (0 si pierde)."""
    if bet_type == "color":
        return 1 if color_of(result) == selection and selection in ("red", "black") else 0
    if bet_type == "number":
        return 35 if int(selection) == result else 0
    return 0


def spin(db: Session, user: User, bet_type: str, selection, amount: float) -> dict:
    """Gira la ruleta, liquida sobre el saldo y devuelve el resultado."""
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise RouletteError("invalid_amount")
    if amount < MIN_BET or amount > user.balance:
        raise RouletteError("invalid_amount")

    if bet_type == "color":
        if selection not in ("red", "black", "green"):
            raise RouletteError("invalid_selection")
        if selection == "green":  # apostar al 0
            bet_type, selection = "number", 0
    if bet_type == "number":
        try:
            selection = int(selection)
        except (TypeError, ValueError):
            raise RouletteError("invalid_selection")
        if not 0 <= selection <= 36:
            raise RouletteError("invalid_selection")

    result = secrets.randbelow(37)  # 0..36, justo
    mult = _payout_multiplier(bet_type, selection, result)
    delta = round(amount * mult, 2) if mult > 0 else -amount
    user.balance = round(user.balance + delta, 2)
    db.add(BalanceLedger(user_id=user.id, bet_id=None, delta=delta, balance_after=user.balance))
    db.commit()

    return {
        "result": result,
        "color": color_of(result),
        "won": mult > 0,
        "delta": delta,
        "balance": user.balance,
    }
