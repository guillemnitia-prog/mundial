"""Tests de la ruleta del casino."""

import pytest
from sqlalchemy import func, select

from src.casino import roulette
from src.casino.roulette import RouletteError, color_of, spin
from src.db.schema import BalanceLedger, User


def _user(db, balance=50.0):
    u = User(username="leo", password_hash="x", has_onboarded=True, balance=balance)
    db.add(u); db.commit()
    return u


def test_color_of():
    assert color_of(0) == "green"
    assert color_of(1) == "red"
    assert color_of(2) == "black"


def test_color_win_pays_1to1(db, monkeypatch):
    u = _user(db, 50.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 1)  # 1 = rojo
    res = spin(db, u, "color", "red", 10.0)
    assert res["won"] and res["result"] == 1 and res["color"] == "red"
    assert res["delta"] == 10.0 and u.balance == 60.0


def test_color_loss(db, monkeypatch):
    u = _user(db, 50.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 2)  # 2 = negro
    res = spin(db, u, "color", "red", 10.0)
    assert not res["won"] and res["delta"] == -10.0 and u.balance == 40.0


def test_number_pays_35(db, monkeypatch):
    u = _user(db, 50.0)
    monkeypatch.setattr(roulette.secrets, "randbelow", lambda n: 17)
    res = spin(db, u, "number", 17, 2.0)
    assert res["won"] and res["delta"] == 70.0 and u.balance == 120.0
    assert db.execute(select(func.count(BalanceLedger.id))).scalar_one() == 1


def test_invalid_amount(db):
    u = _user(db, 5.0)
    with pytest.raises(RouletteError):
        spin(db, u, "color", "red", 10.0)  # más que el saldo
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


# --- slots -------------------------------------------------------------------

from src.casino import slots as slots_mod
from src.casino.slots import SlotsError, payout_multiplier
from src.casino.slots import spin as slots_spin


def test_payout_multiplier():
    assert payout_multiplier(["💎", "💎", "💎"]) == 1000
    assert payout_multiplier(["🍒", "🍒", "🍒"]) == 4
    assert payout_multiplier(["🍒", "🍒", "🍋"]) == 1.5  # pareja
    assert payout_multiplier(["🍒", "🍋", "🍒"]) == 1.5  # pareja no adyacente
    assert payout_multiplier(["🍒", "🍋", "🍊"]) == 0.0


def test_slots_triple_win(db, monkeypatch):
    u = _user(db, 50.0)
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: "🍒")
    res = slots_spin(db, u, 1.0)
    assert res["reels"] == ["🍒", "🍒", "🍒"]
    assert res["win"] == 4.0 and res["delta"] == 3.0
    assert u.balance == 53.0


def test_slots_loss(db, monkeypatch):
    u = _user(db, 50.0)
    seq = iter(["🍒", "🍋", "🍊"])
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: next(seq))
    res = slots_spin(db, u, 2.0)
    assert res["win"] == 0.0 and res["delta"] == -2.0
    assert u.balance == 48.0


def test_slots_invalid_amount(db):
    u = _user(db, 5.0)
    with pytest.raises(SlotsError):
        slots_spin(db, u, 10.0)   # más que el saldo
    with pytest.raises(SlotsError):
        slots_spin(db, u, 0.1)    # por debajo del mínimo


def test_slots_endpoint(client, db, monkeypatch):
    from src.auth.users import create_user
    u = create_user(db, "mia", "contrasena123"); u.has_onboarded = True; db.commit()
    monkeypatch.setattr(slots_mod, "_draw_symbol", lambda: "⭐")
    client.post("/auth/login", json={"username": "mia", "password": "contrasena123"})
    r = client.post("/casino/slots", json={"amount": 0.5})
    assert r.status_code == 200
    assert r.json()["reels"] == ["⭐", "⭐", "⭐"] and r.json()["win"] == 20.0
