"""Tests de los endpoints de lectura para la PWA (Fase 11A)."""

from datetime import datetime, timezone

from src.auth.users import create_user
from src.db.schema import Match, Prediction, Team


def _onboarded_login(client, db, username="leo", balance=50.0):
    u = create_user(db, username, "contrasena123")
    u.has_onboarded = True
    u.balance = balance
    db.commit()
    client.post("/auth/login", json={"username": username, "password": "contrasena123"})
    return u


def _match_with_pick(db, analyzed=True):
    home = Team(name="Spain", fifa_code="ESP", elo=2157, is_host=False)
    away = Team(name="Brazil", fifa_code="BRA", elo=1991, is_host=False)
    db.add_all([home, away])
    db.commit()
    m = Match(home_id=home.id, away_id=away.id, stage="group", group_label="A",
              status="scheduled", neutral_venue=True,
              utc_date=datetime(2026, 6, 15, 19, tzinfo=timezone.utc),
              analysis_status="analyzed" if analyzed else "pending",
              analysis_stage="preliminary" if analyzed else None)
    db.add(m)
    db.commit()
    p = Prediction(match_id=m.id, market="1x2", outcome="home", model_prob=0.78,
                   fair_prob=0.62, offered_odds=1.75, ev=0.365, recommended_stake=0.05,
                   rank=1, confidence="alta")
    db.add(p)
    db.commit()
    return m, p


def test_list_matches(client, db):
    _onboarded_login(client, db)
    _match_with_pick(db)
    resp = client.get("/matches")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["state"] == "analizado"
    assert data[0]["home"] == "Spain"
    assert data[0]["n_picks"] == 1


def test_match_detail_with_pick_and_stake(client, db):
    _onboarded_login(client, db, balance=50.0)
    m, p = _match_with_pick(db)
    resp = client.get(f"/matches/{m.id}")
    assert resp.status_code == 200
    d = resp.json()
    assert d["home"]["elo"] == 2157
    assert d["state"] == "analizado"
    assert len(d["picks"]) == 1
    pick = d["picks"][0]
    assert pick["confidence"] == "alta"
    assert pick["ev_pct"] == 36.5
    assert pick["stake_eur"] == 2.5   # 50 · 0.05
    assert pick["stake_pct"] == 5.0
    assert pick["your_decision"] is None
    assert "proxy" in d["odds_proxy_notice"].lower()
    assert d["message"] is None


def test_match_detail_no_value(client, db):
    _onboarded_login(client, db)
    home = Team(name="Iran", fifa_code="IRN")
    away = Team(name="Qatar", fifa_code="QAT")
    db.add_all([home, away])
    db.commit()
    m = Match(home_id=home.id, away_id=away.id, stage="group", status="scheduled")
    db.add(m)
    db.commit()
    resp = client.get(f"/matches/{m.id}")
    assert resp.status_code == 200
    assert resp.json()["picks"] == []
    assert resp.json()["message"] == "Sin apuesta de valor en este partido"


def test_ranking_and_balance(client, db):
    _onboarded_login(client, db, "leo", balance=60.0)
    create_user(db, "mia", "x")
    db.commit()
    resp = client.get("/ranking")
    assert resp.status_code == 200
    rows = resp.json()
    assert rows[0]["username"] == "leo"  # mayor saldo primero
    assert rows[0]["balance"] == 60.0

    bal = client.get("/me/balance")
    assert bal.status_code == 200
    assert bal.json()["balance"] == 60.0


def test_views_require_onboarding(client, db):
    create_user(db, "noob", "contrasena123")  # sin has_onboarded
    db.commit()
    client.post("/auth/login", json={"username": "noob", "password": "contrasena123"})
    assert client.get("/matches").status_code == 403  # onboarding_required
