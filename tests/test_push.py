"""Tests de Web Push (Fase 13). Sin red: pywebpush.webpush mockeado."""

import dataclasses

import pytest
from sqlalchemy import func, select

from src.config import settings
from src.db.schema import PushSubscription, User
from src.notifications import events, push


def _enable_vapid(monkeypatch, *modules):
    repl = dataclasses.replace(settings, vapid_private_key="priv", vapid_public_key="pub",
                               vapid_subject="mailto:test@example.com")
    for m in modules:
        monkeypatch.setattr(f"{m}.settings", repl)


def _user(db, name="leo"):
    u = User(username=name, password_hash="x", has_onboarded=True)
    db.add(u)
    db.commit()
    return u


def _sub(db, user_id, endpoint="https://push.example/abc"):
    s = PushSubscription(user_id=user_id, endpoint=endpoint, p256dh="k", auth="a")
    db.add(s)
    db.commit()
    return s


# --- envío ------------------------------------------------------------------

def test_send_to_user_calls_webpush(db, monkeypatch):
    _enable_vapid(monkeypatch, "src.notifications.push")
    u = _user(db)
    _sub(db, u.id)
    calls = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: calls.append(kw))

    sent = push.send_to_user(db, u.id, {"title": "hola", "body": "x"})
    assert sent == 1
    assert len(calls) == 1
    assert calls[0]["vapid_private_key"] == "priv"


def test_expired_subscription_is_purged(db, monkeypatch):
    _enable_vapid(monkeypatch, "src.notifications.push")
    u = _user(db)
    _sub(db, u.id)

    from pywebpush import WebPushException

    class _Resp:
        status_code = 410

    def boom(**kw):
        raise WebPushException("gone", response=_Resp())

    monkeypatch.setattr("pywebpush.webpush", boom)
    sent = push.send_to_user(db, u.id, {"title": "x"})
    assert sent == 0
    assert db.execute(select(func.count(PushSubscription.id))).scalar_one() == 0  # purgada


def test_no_vapid_is_noop(db, monkeypatch):
    u = _user(db)
    _sub(db, u.id)
    # settings.vapid_private_key vacío por defecto → no-op.
    called = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: called.append(kw))
    assert push.send_to_user(db, u.id, {"title": "x"}) == 0
    assert called == []


# --- enrutado de dispatch ---------------------------------------------------

def test_dispatch_routes_user_vs_broadcast(db, monkeypatch):
    _enable_vapid(monkeypatch, "src.notifications.push")
    a = _user(db, "ana"); b = _user(db, "leo")
    _sub(db, a.id, "https://push.example/a")
    _sub(db, b.id, "https://push.example/b")
    calls = []
    monkeypatch.setattr("pywebpush.webpush", lambda **kw: calls.append(kw))

    # Payload dirigido a un usuario → 1 envío.
    n1 = events.dispatch([{"user_id": a.id, "title": "tuyo"}], db)
    assert n1 == 1

    # Payload broadcast (sin user_id) → a todas las suscripciones (2).
    n2 = events.dispatch([{"title": "para todos"}], db)
    assert n2 == 2


# --- endpoints --------------------------------------------------------------

def test_push_endpoints(client, db, monkeypatch):
    _enable_vapid(monkeypatch, "src.api.push")
    from src.auth.users import create_user
    create_user(db, "leo", "contrasena123")
    db.commit()
    client.post("/auth/login", json={"username": "leo", "password": "contrasena123"})

    key = client.get("/push/vapid-public-key")
    assert key.status_code == 200 and key.json()["key"] == "pub"

    body = {"endpoint": "https://push.example/xyz", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/push/subscribe", json=body).status_code == 201
    # Upsert: misma endpoint no duplica.
    assert client.post("/push/subscribe", json=body).status_code == 201
    assert db.execute(select(func.count(PushSubscription.id))).scalar_one() == 1


def test_subscribe_requires_auth(client):
    body = {"endpoint": "https://push.example/zzz", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/push/subscribe", json=body).status_code == 401
