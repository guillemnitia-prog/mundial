"""Tests del chat WebSocket (Fase 10)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from starlette.websockets import WebSocketDisconnect

from src.auth.users import create_user
from src.chat.manager import ConnectionManager
from src.db.schema import ChatMessage, User


# --- ConnectionManager (async) ---------------------------------------------

class _FakeWS:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    async def accept(self):
        pass

    async def send_json(self, message):
        if self.fail:
            raise RuntimeError("conexión muerta")
        self.sent.append(message)


async def test_manager_broadcasts_to_all():
    m = ConnectionManager()
    a, b = _FakeWS(), _FakeWS()
    await m.connect(a, "ana")
    await m.connect(b, "leo")
    await m.broadcast({"x": 1})
    assert a.sent == [{"x": 1}] and b.sent == [{"x": 1}]


async def test_manager_dead_connection_does_not_break_others():
    m = ConnectionManager()
    good, bad = _FakeWS(), _FakeWS(fail=True)
    await m.connect(bad, "x")
    await m.connect(good, "y")
    await m.broadcast({"hola": True})
    assert good.sent == [{"hola": True}]
    assert len(m.active) == 1  # la muerta se descartó


# --- helpers integración ---------------------------------------------------

def _login(client, db, username="leo"):
    create_user(db, username, "contrasena123")
    db.commit()
    client.post("/auth/login", json={"username": username, "password": "contrasena123"})


# --- auth -------------------------------------------------------------------

def test_ws_requires_auth(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/chat"):
            pass


# --- historial + eco --------------------------------------------------------

def test_history_and_echo_and_persist(client, db):
    _login(client, db, "leo")
    with client.websocket_connect("/ws/chat") as ws:
        hist = ws.receive_json()
        assert hist["type"] == "history" and hist["messages"] == []

        ws.send_text("¡hola equipo!")
        msg = ws.receive_json()
        assert msg["type"] == "message"
        assert msg["username"] == "leo"
        assert msg["content"] == "¡hola equipo!"

    # Persistido en chat_messages.
    assert db.execute(select(func.count(ChatMessage.id))).scalar_one() == 1


def test_blank_messages_ignored(client, db):
    _login(client, db, "mia")
    with client.websocket_connect("/ws/chat") as ws:
        ws.receive_json()  # history
        ws.send_text("   ")  # en blanco → ignorado
        ws.send_text("real")
        msg = ws.receive_json()
        assert msg["content"] == "real"
    assert db.execute(select(func.count(ChatMessage.id))).scalar_one() == 1


def test_history_limited_to_50(client, db):
    user = create_user(db, "noa", "contrasena123")
    db.commit()
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    for i in range(55):
        db.add(ChatMessage(user_id=user.id, content=f"m{i}", created_at=base + timedelta(minutes=i)))
    db.commit()

    client.post("/auth/login", json={"username": "noa", "password": "contrasena123"})
    with client.websocket_connect("/ws/chat") as ws:
        hist = ws.receive_json()
    assert len(hist["messages"]) == 50
    # Orden cronológico: la última es la más reciente (m54).
    assert hist["messages"][-1]["content"] == "m54"
    assert hist["messages"][0]["content"] == "m5"  # las 50 más recientes (m5..m54)
