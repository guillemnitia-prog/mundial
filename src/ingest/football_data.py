"""Cliente de football-data.org con caché en SQLite (SPEC §1, §9.4).

Ingiere las 48 selecciones y los 104 partidos del Mundial 2026 hacia `teams`/`matches`,
de forma idempotente (upsert por `external_id`). Respeta el límite de 10 req/min y cachea
todas las respuestas: nunca llama a la API si hay una respuesta fresca.

CLI:  python -m src.ingest.football_data
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.schema import Match, Team
from src.db.session import SessionLocal, init_db
from src.ingest.http_cache import RateLimiter, cached_get

SOURCE = "football-data"

# TLA (códigos de 3 letras) de los anfitriones: ventaja local SOLO para ellos.
HOST_TLAS = {"USA", "CAN", "MEX"}

# football-data → nuestro vocabulario (SPEC §2).
STAGE_MAP = {
    "GROUP_STAGE": "group",
    "LAST_32": "R32",
    "LAST_16": "R16",
    "QUARTER_FINALS": "QF",
    "SEMI_FINALS": "SF",
    "THIRD_PLACE": "3RD",
    "FINAL": "F",
}
STATUS_MAP = {
    "SCHEDULED": "scheduled",
    "TIMED": "scheduled",
    "IN_PLAY": "live",
    "PAUSED": "live",
    "FINISHED": "finished",
    "POSTPONED": "postponed",
    "SUSPENDED": "cancelled",
    "CANCELLED": "cancelled",
}

# TTLs: los equipos casi no cambian; los partidos sí durante el torneo.
TEAMS_TTL = 24 * 3600       # 24 h
MATCHES_TTL = 15 * 60       # 15 min


def map_stage(raw: str | None) -> str:
    """Mapea la fase de football-data; fallback seguro a 'group'."""
    return STAGE_MAP.get(raw or "", "group")


def map_status(raw: str | None) -> str:
    """Mapea el estado de football-data; fallback seguro a 'scheduled'."""
    return STATUS_MAP.get(raw or "", "scheduled")


def parse_group(raw: str | None) -> str | None:
    """'GROUP_A' → 'A'; None/otro → None."""
    if raw and raw.upper().startswith("GROUP_"):
        return raw.split("_", 1)[1]
    return None


def _parse_utc(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # football-data usa ISO con 'Z'.
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _default_http_get(url: str, headers: dict, params: dict | None) -> dict:
    """Llamada de red real (httpx). Aislada para poder inyectar una falsa en tests."""
    import httpx

    resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


class FootballDataClient:
    def __init__(self, http_get=None, rate_limiter: RateLimiter | None = None):
        self._http_get = http_get or _default_http_get
        # Free: 10 req/min. Margen: 9/60 s.
        self._limiter = rate_limiter or RateLimiter(max_calls=9, per_seconds=60.0)

    def _get(self, db: Session, path: str, ttl: int) -> dict:
        url = f"{settings.football_data_base_url}{path}"
        cache_key = f"{SOURCE}:{path}"

        def fetcher() -> dict:
            self._limiter.acquire()
            headers = {"X-Auth-Token": settings.football_data_token}
            return self._http_get(url, headers, None)

        return cached_get(db, SOURCE, cache_key, ttl, fetcher)

    def refresh_match(self, db: Session, match, ttl: int = 60) -> None:
        """Actualiza marcador y estado de UN partido desde football-data (cacheado ~60 s)."""
        if not match.external_id:
            return
        try:
            data = self._get(db, f"/matches/{match.external_id}", ttl)
        except Exception:
            return
        m = data.get("match", data) if isinstance(data, dict) else {}
        ft = (m.get("score") or {}).get("fullTime") or {}
        new_status = map_status(m.get("status"))
        match.status = new_status
        match.home_goals = ft.get("home")
        match.away_goals = ft.get("away")
        db.commit()

    # --- Ingesta -----------------------------------------------------------

    def ingest_teams(self, db: Session) -> int:
        comp = settings.football_data_competition
        data = self._get(db, f"/competitions/{comp}/teams", TEAMS_TTL)
        count = 0
        for t in data.get("teams", []):
            ext_id = t.get("id")
            tla = t.get("tla")
            team = db.execute(
                select(Team).where(Team.external_id == ext_id)
            ).scalar_one_or_none()
            if team is None:
                team = Team(external_id=ext_id, name=t.get("name"))
                db.add(team)
            team.name = t.get("name") or team.name
            team.fifa_code = tla
            team.confederation = (t.get("area") or {}).get("name")
            team.is_host = tla in HOST_TLAS
            count += 1
        db.commit()
        return count

    def ingest_matches(self, db: Session) -> int:
        comp = settings.football_data_competition
        data = self._get(db, f"/competitions/{comp}/matches", MATCHES_TTL)

        # Índice external_id → (team_id, is_host) para resolver rivales.
        teams = {
            t.external_id: t
            for t in db.execute(select(Team)).scalars().all()
            if t.external_id is not None
        }

        count = 0
        for m in data.get("matches", []):
            ext_id = m.get("id")
            home_ext = (m.get("homeTeam") or {}).get("id")
            away_ext = (m.get("awayTeam") or {}).get("id")
            home = teams.get(home_ext)
            away = teams.get(away_ext)

            ft = (m.get("score") or {}).get("fullTime") or {}
            is_host_match = bool((home and home.is_host) or (away and away.is_host))

            match = db.execute(
                select(Match).where(Match.external_id == ext_id)
            ).scalar_one_or_none()
            if match is None:
                match = Match(external_id=ext_id)
                db.add(match)

            match.utc_date = _parse_utc(m.get("utcDate"))
            match.home_id = home.id if home else None
            match.away_id = away.id if away else None
            match.group_label = parse_group(m.get("group"))
            match.stage = map_stage(m.get("stage"))
            match.status = map_status(m.get("status"))
            match.neutral_venue = not is_host_match  # ventaja local solo anfitriones
            match.home_goals = ft.get("home")
            match.away_goals = ft.get("away")
            count += 1
        db.commit()
        return count

    def refresh(self, db: Session) -> dict:
        teams = self.ingest_teams(db)
        matches = self.ingest_matches(db)
        return {"teams": teams, "matches": matches}


def main() -> int:
    init_db()
    if not settings.football_data_token:
        print("Falta FOOTBALL_DATA_TOKEN en .env")
        return 1
    client = FootballDataClient()
    with SessionLocal() as db:
        summary = client.refresh(db)
    print(f"Refresco completado: {summary['teams']} equipos, {summary['matches']} partidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
