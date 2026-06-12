"""Tests del casino (ruleta y slots) con saldo de casino SEPARADO del de apuestas."""

import pytest
from sqlalchemy import func, select

from src.casino import roulette
from src.casino import slots as slots_mod
from src.casino.roulette import RouletteError, color_of, spin
from src.casino.slots import SlotsError, payout_multiplier
from src.casino.slots import spin as slots_spin
from src.db.schema import BalanceLedger, User


def _user(db, casino=20.0, balance=50.0):
    u = User(username="leo", password_hash="x", has_onboarded=True,
             balance=balance, casino_balance=casino)
    db.add(u); db.commit()
    return u


# --- ruleta ------------------------------------------------------------------

def test_color_of():
    assert color_of(0) == "green"
    assert color_of(1) == "red"
    assert color_of(2) == "black"


def test_color_win_pays_1to1_on_casino_balance(db, monkeypatch):
    u = _user(db, casino=20.0, balance=50.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 1)  # 1 = rojo
    res = spin(db, u, "color", "red", 10.0)
    assert res["won"] and res["color"] == "red"
    assert res["delta"] == 10.0 and u.casino_balance == 30.0
    assert u.balance == 50.0  # el saldo de apuestas NO se toca


def test_color_loss(db, monkeypatch):
    u = _user(db, casino=20.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 2)  # 2 = negro
    res = spin(db, u, "color", "red", 10.0)
    assert not res["won"] and res["delta"] == -10.0 and u.casino_balance == 10.0


def test_number_pays_35(db, monkeypatch):
    u = _user(db, casino=20.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 17)
    res = spin(db, u, "number", 17, 2.0)
    assert res["won"] and res["delta"] == 70.0 and u.casino_balance == 90.0
    # El casino no escribe en el ledger de apuestas.
    assert db.execute(select(func.count(BalanceLedger.id))).scalar_one() == 0


def test_invalid_amount(db):
    u = _user(db, casino=5.0)
    with pytest.raises(RouletteError):
        spin(db, u, "color", "red", 10.0)  # más que el saldo de casino
    with pytest.raises(RouletteError):
        spin(db, u, "color", "red", 0)


def test_endpoint(client, db, monkeypatch):
    from src.auth.users import create_user
    u = create_user(db, "leo", "contrasena123"); u.has_onboarded = True; db.commit()
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 0)
    client.post("/auth/login", json={"username": "leo", "password": "contrasena123"})
    r = client.post("/casino/roulette", json={"bet_type": "color", "selection": "green", "amount": 1})
    assert r.status_code == 200
    assert r.json()["result"] == 0 and r.json()["won"] is True  # green=0 paga 35


# --- slots (3x3, línea central) -----------------------------------------------

def test_payout_multiplier():
    assert payout_multiplier(["💎", "💎", "💎"]) == 1000
    assert payout_multiplier(["🍒", "🍒", "🍒"]) == 4
    assert payout_multiplier(["🍒", "🍒", "🍋"]) == 1.5  # pareja
    assert payout_multiplier(["🍒", "🍋", "🍒"]) == 1.5  # pareja no adyacente
    assert payout_multiplier(["🍒", "🍋", "🍊"]) == 0.0


def test_slots_triple_win_on_payline(db, monkeypatch):
    u = _user(db, casino=20.0, balance=50.0)
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: "🍒")
    res = slots_spin(db, u, 1.0)
    assert len(res["columns"]) == 3 and all(len(c) == 3 for c in res["columns"])
    assert res["payline"] == ["🍒", "🍒", "🍒"]
    assert res["win"] == 4.0 and res["delta"] == 3.0
    assert u.casino_balance == 23.0
    assert u.balance == 50.0  # apuestas intactas


def test_slots_loss(db, monkeypatch):
    u = _user(db, casino=20.0)
    # 9 tiradas (3 columnas x 3 filas); la línea central son las posiciones 1,4,7.
    seq = iter(["🍒", "🍒", "🍋", "🍊", "🍋", "🍓", "🍉", "🍊", "⭐"])
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: next(seq))
    res = slots_spin(db, u, 2.0)
    assert res["payline"] == ["🍒", "🍋", "🍊"]
    assert res["win"] == 0.0 and res["delta"] == -2.0
    assert u.casino_balance == 18.0


def test_slots_invalid_amount(db):
    u = _user(db, casino=5.0)
    with pytest.raises(SlotsError):
        slots_spin(db, u, 10.0)   # más que el saldo de casino
    with pytest.raises(SlotsError):
        slots_spin(db, u, 0.1)    # por debajo del mínimo


def test_slots_endpoint(client, db, monkeypatch):
    from src.auth.users import create_user
    u = create_user(db, "mia", "contrasena123"); u.has_onboarded = True; db.commit()
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: "⭐")
    client.post("/auth/login", json={"username": "mia", "password": "contrasena123"})
    r = client.post("/casino/slots", json={"amount": 0.5})
    assert r.status_code == 200
    body = r.json()
    assert body["payline"] == ["⭐", "⭐", "⭐"] and body["win"] == 20.0
    assert "casino_balance" in body
