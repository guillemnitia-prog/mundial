"""Fixtures compartidas: secreto JWT de test, app FastAPI y base de datos temporal."""

import os

# Debe fijarse ANTES de importar src.config (settings se carga en import).
os.environ.setdefault("JWT_SECRET", "test-secret-do-not-use-in-prod-0123456789abcdef")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from src.api.main import create_app  # noqa: E402
from src.db.schema import Base, Team  # noqa: E402
from src.db.session import get_db  # noqa: E402


@pytest.fixture()
def db_engine(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _rec):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def TestSession(db_engine):
    return sessionmaker(bind=db_engine, class_=Session, expire_on_commit=False)


@pytest.fixture()
def db(TestSession):
    with TestSession() as s:
        yield s


@pytest.fixture()
def client(db_engine, TestSession):
    """TestClient con get_db apuntando a la DB temporal."""
    app = create_app()

    def _override_get_db():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seed_teams(db):
    """Siembra un puñado de selecciones para los tests de onboarding."""
    teams = [
        Team(name="Spain", fifa_code="ESP"),
        Team(name="Brazil", fifa_code="BRA"),
        Team(name="France", fifa_code="FRA"),
        Team(name="Argentina", fifa_code="ARG"),
    ]
    db.add_all(teams)
    db.commit()
    return {t.name: t.id for t in teams}
