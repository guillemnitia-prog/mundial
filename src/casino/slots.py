"""Slot de 3 rodillos con saldo virtual. El resultado lo decide el SERVIDOR (justo).

Mecánica clásica de bar: 3 rodillos independientes con símbolos ponderados (las frutas salen
mucho, los diamantes poco). Premios como multiplicador de la apuesta:
- Dos símbolos iguales (cualquier par) → x1.5
- Tres iguales → según el símbolo (ver TRIPLE_PAY; 🍒 x4 … 💎 x1000)

RTP aproximado ~85% (como una slot real). Liquidación neta sobre `users.balance`,
registrada en `balance_ledger` (bet_id NULL).
"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from src.db.schema import BalanceLedger, User

# (símbolo, peso por rodillo). Pesos altos = sale más a menudo.
SYMBOLS: list[tuple[str, int]] = [
    ("🍒", 6), ("🍋", 5), ("🍊", 4), ("🍓", 3), ("🍉", 3),
    ("⭐", 2), ("🔶", 2), ("🔷", 1), ("💎", 1),
]
_TOTAL_WEIGHT = sum(w for _, w in SYMBOLS)

# Multiplicador de la apuesta por TRES iguales.
TRIPLE_PAY = {"🍒": 4, "🍋": 8, "🍊": 12, "🍓": 16, "🍉": 24, "⭐": 40, "🔶": 100, "🔷": 200, "💎": 1000}
PAIR_PAY = 1.5  # dos iguales (cualquier par)

MIN_BET = 0.2
MAX_BET = 100.0


class SlotsError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _draw_symbol() -> str:
    """Un símbolo al azar según los pesos (secrets = aleatoriedad criptográfica)."""
    r = secrets.randbelow(_TOTAL_WEIGHT)
    acc = 0
    for sym, w in SYMBOLS:
        acc += w
        if r < acc:
            return sym
    return SYMBOLS[-1][0]  # inalcanzable


def payout_multiplier(reels: list[str]) -> float:
    """Multiplicador del premio (0 si no hay premio)."""
    a, b, c = reels
    if a == b == c:
        return float(TRIPLE_PAY[a])
    if a == b or a == c or b == c:
        return PAIR_PAY
    return 0.0


def spin(db: Session, user: User, amount: float) -> dict:
    """Tira la slot, liquida sobre el saldo y devuelve el resultado."""
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise SlotsError("invalid_amount")
    if amount < MIN_BET or amount > MAX_BET or amount > user.balance:
        raise SlotsError("invalid_amount")

    reels = [_draw_symbol() for _ in range(3)]
    mult = payout_multiplier(reels)
    win = round(amount * mult, 2)
    delta = round(win - amount, 2)

    user.balance = round(user.balance + delta, 2)
    db.add(BalanceLedger(user_id=user.id, bet_id=None, delta=delta, balance_after=user.balance))
    db.commit()

    return {
        "reels": reels,
        "multiplier": mult,
        "win": win,
        "delta": delta,
        "balance": user.balance,
    }
