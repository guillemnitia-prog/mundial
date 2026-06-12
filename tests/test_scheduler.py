"""Tests de la orquestación del scheduler (Fase 12). Sin red; ensemble pequeño + datos sembrados."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from src.bankroll.bets import record_decision
from src.db.schema import Bet, Match, Odds, Prediction, Team, User
from src.models.dixon_coles import DixonColesModel
from src.models.elo_model import EloModel
from src.models.ensemble import EnsembleModel
from src.notifications import events as notify
from src.scheduler import daily_refresh
from src.scheduler.analysis import analyze_match
from src.scheduler.lifecycle import transition_and_settle


def _ensemble(weight=1.0):
    matches = []
    for i in range(25):
        matches.append(("Spain", "Brazil", 2, 0, date(2023, 1, 1), True))
        matches.append(("Brazil", "Spain", 0, 2, date(2023, 6, 1), True))
    dc = DixonColesModel().fit(matches)
    return EnsembleModel(dc=dc, elo=EloModel(), weight=weight)


def _teams(db):
    spain = Team(name="Spain", fifa_code="ESP", elo=2157.0)
    brazil = Team(name="Brazil", fifa_code="BRA", elo=1991.0)
    db.add_all([spain, brazil])
    db.commit()
    return spain, brazil


def _match(db, spain, brazil, status="scheduled", when=None):
    m = Match(home_id=spain.id, away_id=brazil.id, stage="group", status=status,
              neutral_venue=True, utc_date=when or datetime(2026, 6, 15, 19, tzinfo=timezone.utc))
    db.add(m)
    db.commit()
    return m


def _seed_1x2_odds(db, match_id):
    rows = [
        ("book1", "home", 1.55), ("book1", "draw", 4.0), ("book1", "away", 6.0),
        ("book2", "home", 1.60), ("book2", "draw", 3.8), ("book2", "away", 6.5),
    ]
    for bk, oc, price in rows:
        db.add(Odds(match_id=match_id, bookmaker=bk, market="1x2", outcome=oc, price=price))
    db.commit()


def _user(db, name, balance=50.0):
    u = User(username=name, password_hash="x", has_onboarded=True, balance=balance)
    db.add(u)
    db.commit()
    return u


# --- analyze_match ---------------------------------------------------------

def test_analyze_match_produces_value_pick(db):
    spain, brazil = _teams(db)
    m = _match(db, spain, brazil)
    _seed_1x2_odds(db, m.id)
    picks = analyze_match(db, m, _ensemble(), stage="preliminary")

    assert len(picks) >= 1
    assert picks[0]["outcome"] == "home"  # España, fuerte favorito
    pred = db.execute(select(Prediction).where(Prediction.match_id == m.id, Prediction.outcome == "home")).scalar_one()
    assert pred.recommended_stake == pytest.approx(0.20)  # suelo de política (20%)
    assert pred.confidence in ("alta", "media")
    db.refresh(m)
    assert m.analysis_status == "analyzed" and m.analysis_stage == "preliminary"


def test_analyze_match_no_odds_no_picks(db):
    spain, brazil = _teams(db)
    m = _match(db, spain, brazil)
    picks = analyze_match(db, m, _ensemble())
    assert picks == []
    db.refresh(m)
    assert m.analysis_status == "analyzed"  # analizado aunque sin value


def test_reanalysis_upserts_and_preserves_bet_link(db):
    spain, brazil = _teams(db)
    m = _match(db, spain, brazil)
    _seed_1x2_odds(db, m.id)
    analyze_match(db, m, _ensemble(), stage="preliminary")
    pred = db.execute(select(Prediction).where(Prediction.match_id == m.id, Prediction.rank == 1)).scalar_one()
    pred_id = pred.id

    u = _user(db, "leo")
    record_decision(db, u, pred, "accept")

    # Re-análisis final: misma predicción (mismo id), sin duplicar.
    analyze_match(db, m, _ensemble(), stage="final")
    assert db.execute(select(func.count(Prediction.id)).where(Prediction.match_id == m.id, Prediction.outcome == "home")).scalar_one() == 1
    pred2 = db.execute(select(Prediction).where(Prediction.match_id == m.id, Prediction.outcome == "home")).scalar_one()
    assert pred2.id == pred_id
    bet = db.execute(select(Bet).where(Bet.user_id == u.id)).scalar_one()
    assert bet.prediction_id == pred_id


def test_fallback_elo_only_when_team_not_in_dc(db):
    # Iran/Qatar no están en el DC (entrenado solo con Spain/Brazil) pero tienen Elo.
    iran = Team(name="Iran", fifa_code="IRN", elo=1700.0)
    qatar = Team(name="Qatar", fifa_code="QAT", elo=1450.0)
    db.add_all([iran, qatar])
    db.commit()
    m = Match(home_id=iran.id, away_id=qatar.id, stage="group", status="scheduled", neutral_venue=True,
              utc_date=datetime(2026, 6, 15, 19, tzinfo=timezone.utc))
    db.add(m)
    db.commit()
    _seed_1x2_odds(db, m.id)
    analyze_match(db, m, _ensemble())  # no debe lanzar KeyError
    db.refresh(m)
    assert m.analysis_status == "analyzed"


# --- lifecycle -------------------------------------------------------------

def test_lifecycle_materialize_and_settle(db):
    spain, brazil = _teams(db)
    m = _match(db, spain, brazil)
    _seed_1x2_odds(db, m.id)
    analyze_match(db, m, _ensemble())
    pred = db.execute(select(Prediction).where(Prediction.match_id == m.id, Prediction.rank == 1)).scalar_one()

    interactor = _user(db, "leo", 50.0)
    passive = _user(db, "mia", 50.0)
    record_decision(db, interactor, pred, "accept")  # stake 2.50

    # Partido en vivo → materializar defaults (mia entra con 'default').
    m.status = "live"
    db.commit()
    res = transition_and_settle(db)
    assert res["defaults_materialized"] == 1
    mia_bet = db.execute(select(Bet).where(Bet.user_id == passive.id)).scalar_one()
    assert mia_bet.decision == "default"

    # Partido finalizado, gana España (home) → liquidar a ambos.
    m.status = "finished"
    m.home_goals, m.away_goals = 2, 0
    db.commit()
    res2 = transition_and_settle(db)
    assert len(res2["settlement_events"]) == 2
    db.refresh(interactor)
    assert interactor.balance > 50.0  # ganó

    # Idempotente: segunda pasada no re-liquida.
    res3 = transition_and_settle(db)
    assert res3["settlement_events"] == []


# --- notifications ---------------------------------------------------------

def test_notification_templates(db):
    spain, brazil = _teams(db)
    m = _match(db, spain, brazil, status="finished")
    m.home_goals, m.away_goals = 2, 0
    db.commit()
    u = _user(db, "leo", 53.75)
    won = Bet(user_id=u.id, match_id=m.id, market="1x2", outcome="home", stake=2.5, odds=1.6,
              decision="recommended", status="won")
    db.add(won); db.commit()
    msg = notify.settlement_message(db, u, won, m)
    assert "ganada" in msg["title"] and "Spain vs Brazil" in msg["title"]
    assert "Saldo actual: 53,75" in msg["body"]

    pre = notify.pre_match_message(db, m, "home", 1.6, 2.5)
    assert "En 1 hora" in pre["title"] and "stake sugerido: 2,50" in pre["body"]


# --- daily_refresh end-to-end ----------------------------------------------

class _FakeClient:
    def refresh(self, db): return {}
    def ingest_odds(self, db): return {}


def test_daily_refresh_end_to_end(db):
    spain, brazil = _teams(db)
    now = datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)

    # Partido de hoy con odds → se analizará.
    today_match = _match(db, spain, brazil, when=datetime(2026, 6, 15, 19, tzinfo=timezone.utc))
    _seed_1x2_odds(db, today_match.id)

    # Partido finalizado con apuesta abierta → se liquida + push.
    fin = Match(home_id=spain.id, away_id=brazil.id, stage="group", status="finished",
                neutral_venue=True, home_goals=2, away_goals=0,
                utc_date=datetime(2026, 6, 14, 19, tzinfo=timezone.utc))
    db.add(fin); db.commit()
    u = _user(db, "leo", 50.0)
    db.add(Bet(user_id=u.id, match_id=fin.id, market="1x2", outcome="home", stake=5.0, odds=2.0,
               decision="recommended", status="open"))
    db.commit()

    summary = daily_refresh.run(
        db, now=now, fd_client=_FakeClient(), elo_ingest=lambda d: None,
        odds_client=_FakeClient(), ensemble=_ensemble(),
    )
    assert summary["settled"] == 1   # una liquidación (genera payload de push)
    assert summary["push"] == 0      # sin VAPID/suscripción el envío es no-op (ver test_push)
    assert summary["analyzed"] == 1  # el partido de hoy
    db.refresh(u)
    assert u.balance == pytest.approx(55.0)  # ganó 5·(2-1)
