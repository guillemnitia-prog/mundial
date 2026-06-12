"""Tests de decisión de apuesta por usuario y liquidación por importe efectivo (SPEC §5.3)."""

import pytest
from sqlalchemy import func, select

from datetime import datetime, timedelta, timezone

from src.bankroll.bets import (
    BettingError,
    betting_open,
    materialize_default_bets,
    record_decision,
    recommended_eur,
    undo_decision,
)
from src.bankroll.settle import bet_won, settle_match
from src.db.schema import BalanceLedger, Bet, Match, Prediction, Team, User


# --- helpers ---------------------------------------------------------------

def _setup_match(db, status="scheduled", home_goals=None, away_goals=None):
    home = Team(name="Spain")
    away = Team(name="Brazil")
    db.add_all([home, away])
    db.commit()
    m = Match(home_id=home.id, away_id=away.id, stage="group", status=status,
              home_goals=home_goals, away_goals=away_goals)
    db.add(m)
    db.commit()
    return m


def _add_prediction(db, match, market="1x2", outcome="home", odds=2.0, frac=0.05):
    p = Prediction(match_id=match.id, market=market, outcome=outcome, model_prob=0.75,
                   fair_prob=0.6, offered_odds=odds, ev=0.2, recommended_stake=frac, rank=1)
    db.add(p)
    db.commit()
    return p


def _add_user(db, username, balance=50.0, role="member"):
    u = User(username=username, password_hash="x", role=role, has_onboarded=True, balance=balance)
    db.add(u)
    db.commit()
    return u


# --- recommended_eur -------------------------------------------------------

def test_recommended_eur():
    u = User(username="a", password_hash="x", balance=50.0)
    p = Prediction(match_id=1, market="1x2", outcome="home", model_prob=0.75,
                   fair_prob=0.6, offered_odds=2.0, ev=0.2, recommended_stake=0.20)
    assert recommended_eur(u, p) == 10.0  # max(20% de 50, 10€) = 10


# --- record_decision -------------------------------------------------------

def test_accept_uses_recommended(db):
    m = _setup_match(db)
    p = _add_prediction(db, m, frac=0.05)
    u = _add_user(db, "leo", balance=50.0)

    bet = record_decision(db, u, p, "accept")
    assert bet.decision == "recommended"
    assert bet.stake == 10.0   # max(20% de 50, 10€)
    assert bet.status == "open"


def test_reject_no_stake(db):
    m = _setup_match(db)
    p = _add_prediction(db, m)
    u = _add_user(db, "leo")
    bet = record_decision(db, u, p, "reject")
    assert bet.decision == "rejected"
    assert bet.stake == 0.0
    assert bet.status == "void"


def test_modify_valid_and_invalid(db):
    m = _setup_match(db)
    p = _add_prediction(db, m)
    u = _add_user(db, "leo", balance=50.0)

    bet = record_decision(db, u, p, "modify", custom_amount=15.0)
    assert bet.decision == "modified"
    assert bet.stake == 15.0

    # Supera el saldo → inválido.
    with pytest.raises(BettingError) as e1:
        record_decision(db, u, p, "modify", custom_amount=999.0)
    assert e1.value.code == "invalid_amount"

    # Por debajo del mínimo (10 €) → inválido.
    with pytest.raises(BettingError) as e2:
        record_decision(db, u, p, "modify", custom_amount=5.0)
    assert e2.value.code == "invalid_amount"


def test_redecide_updates_same_row(db):
    m = _setup_match(db)
    p = _add_prediction(db, m)
    u = _add_user(db, "leo")
    record_decision(db, u, p, "accept")
    record_decision(db, u, p, "modify", custom_amount=15.0)
    assert db.execute(select(func.count(Bet.id))).scalar_one() == 1  # no duplica
    bet = db.execute(select(Bet)).scalar_one()
    assert bet.decision == "modified" and bet.stake == 15.0


def test_betting_locked_when_match_started(db):
    m = _setup_match(db, status="live")
    p = _add_prediction(db, m)
    u = _add_user(db, "leo")
    with pytest.raises(BettingError) as e:
        record_decision(db, u, p, "accept")
    assert e.value.code == "betting_locked"


def test_betting_window_30_min_before(db):
    # Partido programado dentro de 20 min → ventana cerrada (< 30 min).
    m = _setup_match(db)
    m.utc_date = datetime.now(timezone.utc) + timedelta(minutes=20)
    db.commit()
    p = _add_prediction(db, m)
    u = _add_user(db, "leo")
    assert betting_open(m) is False
    with pytest.raises(BettingError) as e:
        record_decision(db, u, p, "accept")
    assert e.value.code == "betting_locked"

    # A 90 min del inicio → abierta.
    m.utc_date = datetime.now(timezone.utc) + timedelta(minutes=90)
    db.commit()
    assert betting_open(m) is True
    assert record_decision(db, u, p, "accept").decision == "recommended"


def test_undo_decision_frees_and_reverts(db):
    m = _setup_match(db)
    m.utc_date = datetime.now(timezone.utc) + timedelta(hours=3)
    db.commit()
    p = _add_prediction(db, m)
    u = _add_user(db, "leo", balance=50.0)

    record_decision(db, u, p, "accept")
    assert db.execute(select(func.count(Bet.id))).scalar_one() == 1

    undo_decision(db, u, p)  # deshacer → borra la fila (dinero disponible de nuevo)
    assert db.execute(select(func.count(Bet.id))).scalar_one() == 0

    # Se puede volver a decidir tras deshacer.
    record_decision(db, u, p, "reject")
    assert db.execute(select(Bet)).scalar_one().decision == "rejected"

    # Deshacer fuera de ventana (a 10 min) → bloqueado.
    m.utc_date = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()
    with pytest.raises(BettingError) as e:
        undo_decision(db, u, p)
    assert e.value.code == "betting_locked"


# --- materialize_default_bets ----------------------------------------------

def test_materialize_defaults_only_non_interacting(db):
    m = _setup_match(db)
    p = _add_prediction(db, m, frac=0.10)
    interacted = _add_user(db, "leo", balance=50.0)
    rejected = _add_user(db, "mia", balance=50.0)
    _passive1 = _add_user(db, "noa", balance=50.0)
    _passive2 = _add_user(db, "iker", balance=30.0)

    record_decision(db, interacted, p, "accept")
    record_decision(db, rejected, p, "reject")

    created = materialize_default_bets(db, p)
    assert created == 2  # solo noa e iker

    defaults = db.execute(select(Bet).where(Bet.decision == "default")).scalars().all()
    names = {db.get(User, b.user_id).username for b in defaults}
    assert names == {"noa", "iker"}
    # importe por defecto (individual): noa 50 → 10 €; iker 30 → 10 € (manda el mínimo)
    noa_bet = next(b for b in defaults if db.get(User, b.user_id).username == "noa")
    iker_bet = next(b for b in defaults if db.get(User, b.user_id).username == "iker")
    assert noa_bet.stake == 10.0
    assert iker_bet.stake == 10.0


# --- bet_won (resolutor) ---------------------------------------------------

def test_bet_won_markets():
    assert bet_won("1x2", "home", 2, 0) is True
    assert bet_won("1x2", "draw", 1, 1) is True
    assert bet_won("1x2", "away", 0, 1) is True
    assert bet_won("1x2", "home", 0, 1) is False
    assert bet_won("over_under", "over_2.5", 2, 1) is True
    assert bet_won("over_under", "under_2.5", 1, 1) is True
    assert bet_won("btts", "yes", 1, 2) is True
    assert bet_won("btts", "no", 0, 3) is True
    assert bet_won("correct_score", "2-0", 2, 0) is True
    assert bet_won("correct_score", "2-0", 1, 0) is False


# --- liquidación con importe efectivo individual ---------------------------

def test_settle_match_individual_effective_amounts(db):
    m = _setup_match(db, home_goals=2, away_goals=0)  # gana "home"
    p = _add_prediction(db, m, market="1x2", outcome="home", odds=2.0, frac=0.05)

    winner = _add_user(db, "leo", balance=50.0)   # acepta recomendado (10 €)
    big = _add_user(db, "mia", balance=50.0)       # modifica a 20 €
    loser_side = _add_user(db, "noa", balance=50.0)  # apuesta a away (perderá)

    record_decision(db, winner, p, "accept")        # stake 10 a home
    record_decision(db, big, p, "modify", custom_amount=20.0)  # stake 20 a home
    # noa apuesta manualmente a 'away' creando otra predicción
    p_away = _add_prediction(db, m, market="1x2", outcome="away", odds=3.0, frac=0.05)
    record_decision(db, loser_side, p_away, "accept")  # stake 10 a away

    # Forzar el partido a finalizado para liquidar.
    m.status = "finished"
    db.commit()

    summary = settle_match(db, m)
    assert summary["settled"] == 3

    db.refresh(winner); db.refresh(big); db.refresh(loser_side)
    # home @2.0 gana: +stake·(2-1)=+stake (importe efectivo individual distinto)
    assert winner.balance == pytest.approx(60.0)   # 50 + 10
    assert big.balance == pytest.approx(70.0)      # 50 + 20
    # away pierde: -10
    assert loser_side.balance == pytest.approx(40.0)

    # Ledger: una fila por apuesta liquidada.
    assert db.execute(select(func.count(BalanceLedger.id))).scalar_one() == 3


def test_settle_match_idempotent_and_skips_rejected(db):
    m = _setup_match(db, home_goals=1, away_goals=1)  # 'home' pierde (empate)
    p = _add_prediction(db, m, market="1x2", outcome="home", odds=2.0, frac=0.10)
    u = _add_user(db, "leo", balance=50.0)
    rej = _add_user(db, "mia", balance=50.0)
    record_decision(db, u, p, "accept")   # stake 10 a home
    record_decision(db, rej, p, "reject")  # fuera

    m.status = "finished"
    db.commit()

    settle_match(db, m)
    db.refresh(u); db.refresh(rej)
    assert u.balance == pytest.approx(40.0)  # pierde 10
    assert rej.balance == pytest.approx(50.0)  # rechazada: intacta

    # Segunda liquidación no vuelve a tocar saldos (idempotente).
    settle_match(db, m)
    db.refresh(u)
    assert u.balance == pytest.approx(40.0)
    assert db.execute(select(func.count(BalanceLedger.id))).scalar_one() == 1


# --- endpoint --------------------------------------------------------------

def test_decision_endpoint(client, db):
    m = _setup_match(db)
    p = _add_prediction(db, m, frac=0.05)
    # Crear usuario con contraseña real para login.
    from src.auth.users import create_user
    u = create_user(db, "leo", "contrasena123")
    u.has_onboarded = True
    db.commit()

    client.post("/auth/login", json={"username": "leo", "password": "contrasena123"})
    resp = client.post(f"/predictions/{p.id}/decision", json={"action": "accept"})
    assert resp.status_code == 200
    assert resp.json()["decision"] == "recommended"

    # Historial.
    mine = client.get("/me/bets")
    assert mine.status_code == 200
    assert len(mine.json()) == 1
