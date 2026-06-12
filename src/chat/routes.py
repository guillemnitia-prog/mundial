"""WebSocket de chat en /ws/chat (SPEC §6.3).

Solo usuarios autenticados (cookie JWT del handshake). Al conectar envía las últimas 50 mensajes;
cada mensaje recibido se persiste en `chat_messages` y se difunde a todos los conectados.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.security import decode_token
from src.auth.users import get_user_by_username
from src.chat.manager import ConnectionManager
from src.config import settings
from src.db.schema import ChatMessage, User
from src.db.session import get_db

router = APIRouter(tags=["chat"])
manager = ConnectionManager()

HISTORY_LIMIT = 50
MAX_CONTENT_LEN = 2000


def get_user_from_ws(websocket: WebSocket, db: Session) -> User | None:
    token = websocket.cookies.get(settings.cookie_name)
    if not token:
        return None
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        return None
    return get_user_by_username(db, payload["sub"])


def _history(db: Session) -> list[dict]:
    rows = db.execute(
        select(ChatMessage, User)
        .join(User, ChatMessage.user_id == User.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    # Devolver en orden cronológico (más antiguo primero).
    return [
        {"username": u.username, "content": m.content, "created_at": m.created_at.isoformat()}
        for (m, u) in reversed(rows)
    ]


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    user = get_user_from_ws(websocket, db)
    if user is None:
        await websocket.close(code=1008)  # Policy Violation: no autenticado
        return

    await manager.connect(websocket, user.username)
    try:
        await websocket.send_json({"type": "history", "messages": _history(db)})
        while True:
            text = await websocket.receive_text()
            content = (text or "").strip()[:MAX_CONTENT_LEN]
            if not content:
                continue
            msg = ChatMessage(user_id=user.id, content=content)
            db.add(msg)
            db.commit()
            db.refresh(msg)
            await manager.broadcast({
                "type": "message",
                "username": user.username,
                "content": content,
                "created_at": msg.created_at.isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
