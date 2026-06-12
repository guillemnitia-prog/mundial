"""Tests de saldo editable: ingresar / retirar / fijar (self-service)."""

import pytest
from sqlalchemy import func, select

from src.bankroll.balance import BalanceError, deposit, set_balance, withdraw
from src.db.schema import BalanceLedger, User


def _user(db, balance=50.0):
    u = User(username="leo", password_hash="x", has_onboarded=True, balance=balance)
    db.add(u)
    db.commit()
    return u


def test_deposit_withdraw_set(db):
    u = _user(db, 50.0)
    deposit(db, u, 30.0)
    assert u.balance == 80.0
    withdraw(db, u, 25.0)
    assert u.balance == 55.0
    set_balance(db, u, 100.0)
    assert u.balance == 100.0
    # Un movimiento en el ledger por cada operación.
    assert db.execute(select(func.count(BalanceLedger.id))).scalar_one() == 3


def test_withdraw_more_than_balance_fails(db):
    u = _user(db, 20.0)
    with pytest.raises(BalanceError) as e:
        withdraw(db, u, 50.0)
    assert e.value.code == "insufficient_funds"
    assert u.balance == 20.0


def test_invalid_amounts(db):
    u = _user(db, 50.0)
    for fn in (deposit, withdraw):
        with pytest.raises(BalanceError):
            fn(db, u, 0)
        with pytest.raises(BalanceError):
            fn(db, u, -5)
    with pytest.raises(BalanceError):
        set_balance(db, u, -1)


# --- endpoints --------------------------------------------------------------

def test_balance_endpoints(client, db):
    from src.auth.users import create_user
    u = create_user(db, "leo", "contrasena123")
    u.has_onboarded = True
    db.commit()
    client.post("/auth/login", json={"username": "leo", "password": "contrasena123"})

    assert client.post("/me/balance/deposit", json={"amount": 20}).json()["balance"] == 70.0
    assert client.post("/me/balance/withdraw", json={"amount": 10}).json()["balance"] == 60.0
    assert client.post("/me/balance/set", json={"amount": 30}).json()["balance"] == 30.0
    # Retirar de más → 422.
    assert client.post("/me/balance/withdraw", json={"amount": 999}).status_code == 422
