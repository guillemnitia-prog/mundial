"""Histórico internacional martj42 (SPEC §1) para entrenar el modelo.

Descarga `results.csv` (cacheado) y lo parsea a filas en memoria. No se vuelca a SQLite (49k+
filas): se usa para ajustar Dixon-Coles y calibrar el ensemble (Fase 7).
"""

from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy.orm import Session

from src.config import settings
from src.ingest.http_cache import RateLimiter, cached_get

SOURCE = "martj42"
RESULTS_TTL = 24 * 3600  # 24 h


def _default_http_get(url: str) -> str:
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def parse_results(text: str) -> list[tuple]:
    """Parsea el CSV martj42 → [(date, home, away, home_goals, away_goals, neutral)].

    Filtra partidos sin marcador (NA, futuros).
    """
    rows: list[tuple] = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        hs, as_ = r.get("home_score"), r.get("away_score")
        if not hs or not as_ or hs == "NA" or as_ == "NA":
            continue
        try:
            d = date.fromisoformat(r["date"])
            hg, ag = int(hs), int(as_)
        except (ValueError, KeyError):
            continue
        neutral = str(r.get("neutral", "")).strip().upper() == "TRUE"
        rows.append((d, r["home_team"], r["away_team"], hg, ag, neutral))
    return rows


def load_results(db: Session, http_get=None, rate_limiter: RateLimiter | None = None) -> list[tuple]:
    """Descarga (cacheada) y parsea el histórico. Devuelve filas ordenadas por fecha."""
    http_get = http_get or _default_http_get
    limiter = rate_limiter or RateLimiter(max_calls=5, per_seconds=60.0)
    url = settings.historical_results_url

    def fetcher() -> dict:
        limiter.acquire()
        return {"csv": http_get(url)}

    data = cached_get(db, SOURCE, f"{SOURCE}:results", RESULTS_TTL, fetcher)
    rows = parse_results(data["csv"])
    rows.sort(key=lambda r: r[0])
    return rows
