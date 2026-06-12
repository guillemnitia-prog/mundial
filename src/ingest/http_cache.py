"""Caché de respuestas HTTP en SQLite + limitador de tasa.

Reutilizable por todos los clientes de `ingest/`. Cumple la regla no negociable: cachear TODO
en SQLite y nunca llamar a una API si hay una respuesta fresca (SPEC §1).
"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.schema import ApiCache


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """Normaliza a UTC consciente (SQLite puede devolver datetimes naive)."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def cached_get(
    db: Session,
    source: str,
    cache_key: str,
    ttl_seconds: int,
    fetcher: Callable[[], dict],
) -> dict:
    """Devuelve la respuesta cacheada si está fresca; si no, llama a `fetcher`, la guarda y la devuelve.

    `fetcher` encapsula la llamada de red real (así los tests inyectan una función falsa).
    """
    now = _utcnow()
    entry = db.execute(
        select(ApiCache).where(ApiCache.cache_key == cache_key)
    ).scalar_one_or_none()

    if entry is not None and _as_aware(entry.expires_at) > now:
        return json.loads(entry.response_json)

    data = fetcher()  # única vía de acceso a la red
    payload = json.dumps(data)
    expires_at = now + timedelta(seconds=ttl_seconds)

    if entry is None:
        db.add(
            ApiCache(
                source=source,
                cache_key=cache_key,
                response_json=payload,
                fetched_at=now,
                expires_at=expires_at,
            )
        )
    else:
        entry.response_json = payload
        entry.fetched_at = now
        entry.expires_at = expires_at
    db.commit()
    return data


class RateLimiter:
    """Limitador de tasa en memoria: como mucho `max_calls` en una ventana de `per_seconds`.

    `acquire()` bloquea (sleep) solo si se alcanzó el límite; si no, retorna de inmediato.
    """

    def __init__(self, max_calls: int, per_seconds: float, sleep: Callable[[float], None] = time.sleep):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._sleep = sleep
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        # Descarta las llamadas fuera de la ventana.
        while self._calls and now - self._calls[0] >= self.per_seconds:
            self._calls.popleft()
        if len(self._calls) >= self.max_calls:
            wait = self.per_seconds - (now - self._calls[0])
            if wait > 0:
                self._sleep(wait)
            now = time.monotonic()
            while self._calls and now - self._calls[0] >= self.per_seconds:
                self._calls.popleft()
        self._calls.append(time.monotonic())
