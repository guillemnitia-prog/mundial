"""Tests del esquema SQLite (Fase 2).

Usan una base de datos temporal aislada (no la de producción) con FK activadas.
"""

import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.db.schema import (
    Base,
    Bet,
    ChampionPick,
    Match,
    Team,
    User,
)

EXPECTED_TABLES = {
    "teams",
    "matches",
    "odds",
    "predictions",
    "users",
    "champion_picks",
    "chat_messages",
    "bets",
    "balance_ledger",
}


@pytest.fixture()
def session(tmp_path):
    """Engine SQLite temporal con FK activadas y tablas creadas."""
    db_file = tmp_path / "test.db"
    eng = create_engine(f"sqlite:///{db_file}", future=True)

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    TestSession = sessionmaker(bind=eng, class_=Session, expire_on_commit=False)
    with TestSession() as s:
        yield s
    eng.dispose()


def test_all_tables_created(session: Session):
    tables = set(inspect(session.get_bind()).get_table_names())
    assert EXPECTED_TABLES.issubset(tables)


def test_user_balance_defaults_to_50(session: Session):
    u = User(username="ana", password_hash="x", role="member")
    session.add(u)
    session.commit()
    session.refresh(u)
    assert u.balance == 50.0  # saldo virtual individual de partida


def test_foreign_keys_enforced(session: Session):
    # Insertar una apuesta con user_id/match_id inexistentes debe fallar (PRAGMA FK on).
    bad = Bet(user_id=999, match_id=999, market="h2h", outcome="home", stake=5.0, odds=1.75)
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()


def test_bet_status_check_constraint(session: Session):
    u = User(username="leo", password_hash="x")
    home = Team(name="Spain")
    away = Team(name="Brazil")
    session.add_all([u, home, away])
    session.commit()
    m = Match(home_id=home.id, away_id=away.id, stage="group", status="scheduled")
    session.add(m)
    session.commit()

    bad = Bet(
        user_id=u.id, match_id=m.id, market="h2h", outcome="home",
        stake=5.0, odds=1.75, status="bogus",  # fuera de {open,won,lost,void}
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()


def test_champion_pick_one_per_user(session: Session):
    u = User(username="mia", password_hash="x")
    t1 = Team(name="France")
    t2 = Team(name="Argentina")
    session.add_all([u, t1, t2])
    session.commit()

    session.add(ChampionPick(user_id=u.id, team_id=t1.id))
    session.commit()
    # Segundo pick del mismo usuario viola la PK (user_id).
    session.add(ChampionPick(user_id=u.id, team_id=t2.id))
    with pytest.raises(IntegrityError):
        session.commit()


def test_match_stage_check_constraint(session: Session):
    home = Team(name="Italy")
    away = Team(name="Germany")
    session.add_all([home, away])
    session.commit()
    bad = Match(home_id=home.id, away_id=away.id, stage="quarterfinal")  # no permitido
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.commit()
