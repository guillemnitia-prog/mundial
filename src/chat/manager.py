"""Gestor de conexiones WebSocket del chat (SPEC §6.3).

Mantiene en memoria las conexiones activas y hace broadcast a todas. Una conexión que falle al
enviar se descarta sin romper el envío al resto.
"""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: list[tuple[WebSocket, str]] = []

    async def connect(self, websocket: WebSocket, username: str) -> None:
        await websocket.accept()
        self.active.append((websocket, username))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active = [(ws, u) for (ws, u) in self.active if ws is not websocket]

    async def broadcast(self, message: dict) -> None:
        dead: list[WebSocket] = []
        for ws, _username in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)
