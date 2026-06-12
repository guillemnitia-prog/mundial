"""Ajustes manuales de saldo por usuario (ingresar / retirar / fijar).

El saldo de partida son 50 € (users.balance DEFAULT 50.0), pero cada usuario puede ingresar o
retirar saldo cuando quiera, o fijarlo a un valor. Cada movimiento se registra en `balance_ledger`
(con `bet_id = NULL`, para distinguirlo de las liquidaciones de apuestas).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.db.schema import BalanceLedger, User

MAX_BALANCE = 1_000_000.0  # tope de cordura para el saldo virtual


class BalanceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _apply(db: Session, user: User, delta: float) -> User:
    new_balance = round(user.balance + delta, 2)
    if new_balance < 0:
        raise BalanceError("insufficient_funds")
    if new_balance > MAX_BALANCE:
        raise BalanceError("amount_too_large")
    user.balance = new_balance
    db.add(BalanceLedger(user_id=user.id, bet_id=None, delta=round(delta, 2), balance_after=new_balance))
    db.commit()
    return user


def deposit(db: Session, user: User, amount: float) -> User:
    """Ingresa `amount` (>0) en el saldo del usuario."""
    if amount is None or amount <= 0:
        raise BalanceError("invalid_amount")
    return _apply(db, user, round(float(amount), 2))


def withdraw(db: Session, user: User, amount: float) -> User:
    """Retira `amount` (>0, ≤ saldo) del saldo del usuario."""
    if amount is None or amount <= 0:
        raise BalanceError("invalid_amount")
    if amount > user.balance:
        raise BalanceError("insufficient_funds")
    return _apply(db, user, -round(float(amount), 2))


def set_balance(db: Session, user: User, new_balance: float) -> User:
    """Fija el saldo del usuario a `new_balance` (≥0). Registra el delta resultante."""
    if new_balance is None or new_balance < 0:
        raise BalanceError("invalid_amount")
    return _apply(db, user, round(float(new_balance) - user.balance, 2))
