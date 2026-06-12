"""Tests de ingest de football-data (Fase 4). Sin red: se inyecta un http_get falso."""

from sqlalchemy import func, select

from src.db.schema import ApiCache, Match, Team
from src.ingest.football_data import (
    FootballDataClient,
    map_stage,
    map_status,
    parse_group,
)
from src.ingest.http_cache import RateLimiter, cached_get


# --- payloads de ejemplo ---------------------------------------------------

TEAMS_PAYLOAD = {
    "teams": [
        {"id": 1, "name": "Mexico", "tla": "MEX", "area": {"name": "Mexico"}},
        {"id": 2, "name": "South Africa", "tla": "RSA", "area": {"name": "South Africa"}},
        {"id": 3, "name": "United States", "tla": "USA", "area": {"name": "United States"}},
        {"id": 4, "name": "Spain", "tla": "ESP", "area": {"name": "Spain"}},
    ]
}

MATCHES_PAYLOAD = {
    "matches": [
        {  # grupo, con anfitrión (México) → no neutral, terminado
            "id": 100, "utcDate": "2026-06-11T19:00:00Z", "group": "GROUP_A",
            "stage": "GROUP_STAGE", "status": "FINISHED",
            "homeTeam": {"id": 1}, "awayTeam": {"id": 2},
            "score": {"fullTime": {"home": 2, "away": 0}},
        },
        {  # grupo, dos no-anfitriones → neutral, sin jugar
            "id": 101, "utcDate": "2026-06-12T16:00:00Z", "group": "GROUP_B",
            "stage": "GROUP_STAGE", "status": "TIMED",
            "homeTeam": {"id": 4}, "awayTeam": {"id": 2},
            "score": {"fullTime": {"home": None, "away": None}},
        },
        {  # eliminatoria sin definir → equipos nulos
            "id": 102, "utcDate": "2026-07-01T19:00:00Z", "group": None,
            "stage": "LAST_32", "status": "TIMED",
            "homeTeam": {"id": None}, "awayTeam": {"id": None},
            "score": {"fullTime": {"home": None, "away": None}},
        },
    ]
}


def _client_returning(payloads):
    """FootballDataClient con http_get falso que responde según el path, contando llamadas."""
    calls = {"n": 0}

    def fake_http_get(url, headers, params):
        calls["n"] += 1
        if "/teams" in url:
            return payloads["teams"]
        return payloads["matches"]

    client = FootballDataClient(http_get=fake_http_get)
    return client, calls


# --- mapeos puros ----------------------------------------------------------

def test_map_stage_and_status():
    assert map_stage("GROUP_STAGE") == "group"
    assert map_stage("LAST_32") == "R32"
    assert map_stage("FINAL") == "F"
    assert map_stage("UNKNOWN") == "group"  # fallback
    assert map_status("FINISHED") == "finished"
    assert map_status("TIMED") == "scheduled"
    assert map_status("WTF") == "scheduled"  # fallback
    assert parse_group("GROUP_C") == "C"
    assert parse_group(None) is None


# --- caché -----------------------------------------------------------------

def test_cached_get_respects_ttl(db):
    calls = {"n": 0}

    def fetcher():
        calls["n"] += 1
        return {"v": calls["n"]}

    first = cached_get(db, "src", "k1", ttl_seconds=60, fetcher=fetcher)
    second = cached_get(db, "src", "k1", ttl_seconds=60, fetcher=fetcher)
    assert first == second == {"v": 1}
    assert calls["n"] == 1  # la 2ª no llama al fetcher

    # Expirar la entrada guardada → la siguiente llamada vuelve a llamar al fetcher.
    from datetime import datetime, timedelta, timezone

    entry = db.execute(select(ApiCache).where(ApiCache.cache_key == "k1")).scalar_one()
    entry.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    third = cached_get(db, "src", "k1", ttl_seconds=60, fetcher=fetcher)
    assert third == {"v": 2}
    assert calls["n"] == 2
    assert db.execute(select(func.count(ApiCache.id))).scalar_one() == 1  # upsert, no duplica


# --- ingesta ---------------------------------------------------------------

def test_ingest_teams_hosts_and_idempotent(db):
    client, calls = _client_returning({"teams": TEAMS_PAYLOAD, "matches": MATCHES_PAYLOAD})

    n1 = client.ingest_teams(db)
    assert n1 == 4
    assert db.execute(select(func.count(Team.id))).scalar_one() == 4

    mex = db.execute(select(Team).where(Team.fifa_code == "MEX")).scalar_one()
    usa = db.execute(select(Team).where(Team.fifa_code == "USA")).scalar_one()
    esp = db.execute(select(Team).where(Team.fifa_code == "ESP")).scalar_one()
    assert mex.is_host and usa.is_host
    assert not esp.is_host

    # Segunda pasada: caché fresca → no más llamadas de red, y sin duplicados.
    client.ingest_teams(db)
    assert calls["n"] == 1
    assert db.execute(select(func.count(Team.id))).scalar_one() == 4


def test_ingest_matches_mapping_and_neutral(db):
    client, _ = _client_returning({"teams": TEAMS_PAYLOAD, "matches": MATCHES_PAYLOAD})
    client.ingest_teams(db)
    n = client.ingest_matches(db)
    assert n == 3
    assert db.execute(select(func.count(Match.id))).scalar_one() == 3

    m_host = db.execute(select(Match).where(Match.external_id == 100)).scalar_one()
    assert m_host.stage == "group" and m_host.status == "finished"
    assert m_host.group_label == "A"
    assert m_host.neutral_venue is False  # juega México (anfitrión)
    assert m_host.home_goals == 2 and m_host.away_goals == 0

    m_neutral = db.execute(select(Match).where(Match.external_id == 101)).scalar_one()
    assert m_neutral.neutral_venue is True  # dos no-anfitriones

    m_ko = db.execute(select(Match).where(Match.external_id == 102)).scalar_one()
    assert m_ko.stage == "R32"
    assert m_ko.home_id is None and m_ko.away_id is None  # rivales sin definir


def test_ingest_matches_idempotent_and_score_update(db):
    payloads = {"teams": TEAMS_PAYLOAD, "matches": MATCHES_PAYLOAD}
    client, _ = _client_returning(payloads)
    client.ingest_teams(db)
    client.ingest_matches(db)

    # Simular actualización de marcador del partido 101 con TTL expirado para forzar refetch.
    from src.ingest import football_data as fd

    payloads["matches"] = {
        "matches": [dict(MATCHES_PAYLOAD["matches"][1], status="FINISHED",
                         score={"fullTime": {"home": 1, "away": 1}})]
    }
    # Forzar expiración de la caché de matches.
    cache = db.execute(
        select(ApiCache).where(ApiCache.cache_key.like("%matches%"))
    ).scalar_one()
    from datetime import datetime, timedelta, timezone
    cache.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    client.ingest_matches(db)
    # Sigue habiendo 3 (no duplica por external_id) y el 101 quedó actualizado.
    assert db.execute(select(func.count(Match.id))).scalar_one() == 3
    m = db.execute(select(Match).where(Match.external_id == 101)).scalar_one()
    assert m.status == "finished" and m.home_goals == 1 and m.away_goals == 1


# --- rate limiter ----------------------------------------------------------

def test_rate_limiter_no_block_under_limit():
    slept = {"t": 0.0}
    rl = RateLimiter(max_calls=9, per_seconds=60.0, sleep=lambda s: slept.__setitem__("t", slept["t"] + s))
    for _ in range(9):
        rl.acquire()
    assert slept["t"] == 0.0  # por debajo del límite no duerme
