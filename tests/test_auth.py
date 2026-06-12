"""Tests de auth y onboarding (Fase 3)."""

from src.auth import seed_users as seed_mod
from src.auth.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.auth.users import create_user
from src.config import settings


# --- helpers ---------------------------------------------------------------

def _make_user(db, username="amigo1", password="contrasena123", role="member"):
    user = create_user(db, username=username, password=password, role=role)
    db.commit()
    return user


def _login(client, username, password):
    return client.post("/auth/login", json={"username": username, "password": password})


# --- security (puro) -------------------------------------------------------

def test_hash_and_verify():
    h = hash_password("s3cret-pass")
    assert h != "s3cret-pass"  # nunca texto plano
    assert h.startswith("$argon2")
    assert verify_password("s3cret-pass", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    token = create_access_token(subject="ana")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "ana"
    assert decode_token("not-a-token") is None


# --- seed_users ------------------------------------------------------------

def test_seed_users_idempotent(TestSession, monkeypatch):
    # Apuntar el seeding a la DB temporal y evitar tocar la DB real.
    monkeypatch.setattr(seed_mod, "SessionLocal", TestSession)
    monkeypatch.setattr(seed_mod, "init_db", lambda: None)

    entries = [{"username": "admin", "password": "x" * 10, "role": "admin"}] + [
        {"username": f"amigo{i}", "password": "x" * 10, "role": "member"} for i in range(1, 7)
    ]

    first = seed_mod.seed_users(entries)
    assert first["created"] == 7

    second = seed_mod.seed_users(entries)  # idempotente
    assert second["created"] == 0
    assert second["skipped"] == 7

    with TestSession() as s:
        from sqlalchemy import func, select

        from src.db.schema import User

        assert s.execute(select(func.count(User.id))).scalar_one() == 7
        admin = s.execute(select(User).where(User.username == "admin")).scalar_one()
        assert admin.role == "admin"


# --- login / cookie --------------------------------------------------------

def test_login_sets_httponly_cookie(client, db):
    _make_user(db, "leo", "contrasena123")
    resp = _login(client, "leo", "contrasena123")
    assert resp.status_code == 200
    assert resp.json()["username"] == "leo"
    # Cookie httpOnly presente.
    assert client.cookies.get(settings.cookie_name)
    assert "httponly" in resp.headers.get("set-cookie", "").lower()


def test_login_bad_credentials(client, db):
    _make_user(db, "leo", "contrasena123")
    resp = _login(client, "leo", "incorrecta")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


def test_me_requires_authentication(client, db):
    assert client.get("/auth/me").status_code == 401  # sin cookie
    _make_user(db, "mia", "contrasena123")
    _login(client, "mia", "contrasena123")
    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "mia"
    assert resp.json()["balance"] == 50.0  # saldo individual de partida


# --- onboarding ------------------------------------------------------------

def test_onboarding_flow_and_immutability(client, db, seed_teams):
    _make_user(db, "noa", "contrasena123")
    _login(client, "noa", "contrasena123")

    status_resp = client.get("/onboarding")
    assert status_resp.status_code == 200
    assert status_resp.json()["has_onboarded"] is False
    assert len(status_resp.json()["teams"]) == len(seed_teams)

    pick = client.post("/onboarding/champion", json={"team_id": seed_teams["Spain"]})
    assert pick.status_code == 201
    assert pick.json()["team_name"] == "Spain"

    # has_onboarded ya es True.
    assert client.get("/auth/me").json()["has_onboarded"] is True

    # Inmutable: segundo intento rechazado.
    again = client.post("/onboarding/champion", json={"team_id": seed_teams["Brazil"]})
    assert again.status_code == 409
    assert again.json()["detail"] == "champion_already_set"


def test_champion_picks_requires_onboarding(client, db, seed_teams):
    _make_user(db, "iker", "contrasena123")
    _login(client, "iker", "contrasena123")

    # Antes de onboardear: bloqueado.
    blocked = client.get("/champion-picks")
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "onboarding_required"

    client.post("/onboarding/champion", json={"team_id": seed_teams["France"]})
    ok = client.get("/champion-picks")
    assert ok.status_code == 200
    assert any(p["username"] == "iker" for p in ok.json())


# --- admin -----------------------------------------------------------------

def test_admin_reset_password_permissions(client, db):
    _make_user(db, "boss", "contrasena123", role="admin")
    _make_user(db, "member1", "contrasena123", role="member")

    # Un member no puede resetear.
    _login(client, "member1", "contrasena123")
    forbidden = client.post(
        "/auth/admin/reset-password",
        json={"username": "member1", "new_password": "nuevaclave123"},
    )
    assert forbidden.status_code == 403

    # El admin sí.
    _login(client, "boss", "contrasena123")
    ok = client.post(
        "/auth/admin/reset-password",
        json={"username": "member1", "new_password": "nuevaclave123"},
    )
    assert ok.status_code == 200

    # La nueva contraseña funciona.
    assert _login(client, "member1", "nuevaclave123").status_code == 200
