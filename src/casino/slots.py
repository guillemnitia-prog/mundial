"""Slot de 3 columnas × 3 filas con saldo de CASINO (separado del de apuestas).

El servidor genera la parrilla completa (3 rodillos que "caen", 3 símbolos visibles por rodillo)
y paga sobre la LÍNEA CENTRAL (línea de premio), al estilo clásico:
- Dos símbolos iguales en la línea (cualquier par) → x1.5
- Tres iguales en la línea → según el símbolo (🍒 x4 … 💎 x1000)

RTP aproximado ~85%. Usa `users.casino_balance` (20 € de partida); NUNCA toca el saldo
de apuestas (`users.balance`).
"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from src.db.schema import User

# (símbolo, peso por rodillo). Pesos altos = sale más a menudo.
SYMBOLS: list[tuple[str, int]] = [
    ("🍒", 6), ("🍋", 5), ("🍊", 4), ("🍓", 3), ("🍉", 3),
    ("⭐", 2), ("🔶", 2), ("🔷", 1), ("💎", 1),
]
_TOTAL_WEIGHT = sum(w for _, w in SYMBOLS)

# Multiplicador de la apuesta por TRES iguales en la línea central.
TRIPLE_PAY = {"🍒": 4, "🍋": 8, "🍊": 12, "🍓": 16, "🍉": 24, "⭐": 40, "🔶": 100, "🔷": 200, "💎": 1000}
PAIR_PAY = 1.5  # dos iguales en la línea (cualquier par)

MIN_BET = 0.2
MAX_BET = 100.0

ROWS = 3
COLS = 3


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


def payout_multiplier(payline: list[str]) -> float:
    """Multiplicador del premio para la línea central (0 si no hay premio)."""
    a, b, c = payline
    if a == b == c:
        return float(TRIPLE_PAY[a])
    if a == b or a == c or b == c:
        return PAIR_PAY
    return 0.0


def spin(db: Session, user: User, amount: float) -> dict:
    """Tira la slot, liquida sobre el saldo de CASINO y devuelve la parrilla 3x3."""
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise SlotsError("invalid_amount")
    if amount < MIN_BET or amount > MAX_BET or amount > user.casino_balance:
        raise SlotsError("invalid_amount")

    # columns[i] = [arriba, CENTRO, abajo] del rodillo i. La línea de premio es el centro.
    columns = [[_draw_symbol() for _ in range(ROWS)] for _ in range(COLS)]
    payline = [col[1] for col in columns]
    mult = payout_multiplier(payline)
    win = round(amount * mult, 2)
    delta = round(win - amount, 2)

    user.casino_balance = round(user.casino_balance + delta, 2)
    db.commit()

    return {
        "columns": columns,
        "payline": payline,
        "multiplier": mult,
        "win": win,
        "delta": delta,
        "casino_balance": user.casino_balance,
    }
