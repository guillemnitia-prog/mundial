"""Tests del ingest de Elo (Fase 6). Sin red: http_get falso + fixture."""

from sqlalchemy import select

from src.db.schema import Team
from src.ingest.elo import ingest_elo, parse_world_tsv

# TSV de muestra (col0 rank, col1, col2 code, col3 rating, ...). ES/BR/FR/AR + XX sin match.
SAMPLE_TSV = "\n".join([
    "1\t1\tES\t2157\t1\t2189",
    "2\t2\tAR\t2115\t1\t2172",
    "3\t3\tFR\t2063\t1\t2135",
    "4\t10\tBR\t2010\t2\t2100",
    "5\t5\tXX\t1500\t0\t1500",  # código inexistente en nuestros equipos
    "linea basura sin tabs",
])


def _seed(db):
    db.add_all([
        Team(name="Spain", fifa_code="ESP"),
        Team(name="Brazil", fifa_code="BRA"),
        Team(name="France", fifa_code="FRA"),
        Team(name="Argentina", fifa_code="ARG"),
        Team(name="Nowhere", fifa_code="ZZZ"),  # sin code en el mapa → unmatched
    ])
    db.commit()


def test_parse_world_tsv():
    ratings = parse_world_tsv(SAMPLE_TSV)
    assert ratings["ES"] == 2157
    assert ratings["BR"] == 2010
    assert "XX" in ratings
    assert "linea" not in ratings  # línea basura ignorada


def test_ingest_elo_matches_and_idempotent(db):
    _seed(db)
    calls = {"n": 0}

    def fake_http_get(url):
        calls["n"] += 1
        return SAMPLE_TSV

    summary = ingest_elo(db, http_get=fake_http_get)
    assert summary["matched"] == 4  # ES, BR, FR, AR
    assert "ZZZ" in summary["unmatched"]

    esp = db.execute(select(Team).where(Team.fifa_code == "ESP")).scalar_one()
    assert esp.elo == 2157.0

    # Segunda pasada: caché fresca → no más red, sin romper, mismo resultado.
    ingest_elo(db, http_get=fake_http_get)
    assert calls["n"] == 1
    esp2 = db.execute(select(Team).where(Team.fifa_code == "ESP")).scalar_one()
    assert esp2.elo == 2157.0
