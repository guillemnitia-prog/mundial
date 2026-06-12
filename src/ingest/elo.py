"""Ingest de ratings Elo de selecciones desde eloratings.net (SPEC §1, §9.6).

Descarga el TSV mundial (cacheado), lo parsea y puebla `teams.elo` haciendo match por el código
de 2 letras de eloratings (≈ ISO alpha-2, con excepciones tipo EN/SC). Selecciones, NUNCA ClubElo.

CLI:  python -m src.ingest.elo
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.schema import Team
from src.db.session import SessionLocal, init_db
from src.ingest.http_cache import RateLimiter, cached_get

SOURCE = "eloratings"
ELO_TTL = 7 * 24 * 3600  # 7 días (los Elo cambian poco)

# Código TLA de football-data → código de 2 letras de eloratings (48 selecciones del Mundial 2026).
FIFA_TLA_TO_ELO_CODE = {
    "ALG": "DZ", "ARG": "AR", "AUS": "AU", "AUT": "AT", "BEL": "BE", "BIH": "BA",
    "BRA": "BR", "CAN": "CA", "CPV": "CV", "COL": "CO", "COD": "CD", "CRO": "HR",
    "CUW": "CW", "CZE": "CZ", "ECU": "EC", "EGY": "EG", "ENG": "EN", "FRA": "FR",
    "GER": "DE", "GHA": "GH", "HAI": "HT", "IRN": "IR", "IRQ": "IQ", "CIV": "CI",
    "JPN": "JP", "JOR": "JO", "MEX": "MX", "MAR": "MA", "NED": "NL", "NZL": "NZ",
    "NOR": "NO", "PAN": "PA", "PAR": "PY", "POR": "PT", "QAT": "QA", "KSA": "SA",
    "SCO": "SC", "SEN": "SN", "RSA": "ZA", "KOR": "KR", "ESP": "ES", "SWE": "SE",
    "SUI": "CH", "TUN": "TN", "TUR": "TR", "USA": "US", "URY": "UY", "UZB": "UZ",
}


def parse_world_tsv(text: str) -> dict[str, float]:
    """Parsea el TSV de eloratings: col2 = código (2 letras), col3 = rating. → {code: rating}."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        code = parts[2].strip()
        try:
            out[code] = float(parts[3])
        except ValueError:
            continue
    return out


def _default_http_get(url: str) -> str:
    import httpx

    resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0)
    resp.raise_for_status()
    return resp.text


def ingest_elo(db: Session, http_get=None, rate_limiter: RateLimiter | None = None) -> dict:
    """Descarga (cacheado) y puebla teams.elo. Devuelve {matched, unmatched:[fifa_code]}."""
    http_get = http_get or _default_http_get
    limiter = rate_limiter or RateLimiter(max_calls=5, per_seconds=60.0)
    url = settings.eloratings_url

    def fetcher() -> dict:
        limiter.acquire()
        return {"tsv": http_get(url)}

    data = cached_get(db, SOURCE, f"{SOURCE}:world", ELO_TTL, fetcher)
    ratings = parse_world_tsv(data["tsv"])

    matched = 0
    unmatched: list[str] = []
    for team in db.execute(select(Team)).scalars().all():
        code = FIFA_TLA_TO_ELO_CODE.get(team.fifa_code or "")
        rating = ratings.get(code) if code else None
        if rating is None:
            unmatched.append(team.fifa_code or team.name)
            continue
        team.elo = rating
        matched += 1
    db.commit()
    return {"matched": matched, "unmatched": unmatched}


def main() -> int:
    init_db()
    with SessionLocal() as db:
        summary = ingest_elo(db)
    print(f"Elo ingerido: {summary['matched']} equipos. Sin match: {summary['unmatched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
