"""Cliente de The Odds API con caché y presupuesto de créditos (SPEC §1, §9.8).

Trae cuotas region=eu (proxy de Bet365.es/Sportium — AVISAR de la diferencia), normaliza los
mercados al vocabulario del modelo y las guarda en `odds`. Respeta el límite de 500 créditos/mes
con un contador en `api_usage` que CORTA antes de excederse. Nunca llama si hay respuesta fresca.

The Odds API no incluye Pinnacle: la línea sharp se aproxima por el consenso eu (ver value/devig).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.schema import ApiUsage, Match, Odds, Team
from src.db.session import SessionLocal, init_db
from src.ingest.http_cache import RateLimiter, cached_get

SOURCE = "the-odds-api"
ODDS_TTL = 6 * 3600  # 6 h


class OddsBudgetError(Exception):
    """Se alcanzaría el presupuesto mensual de créditos; no se llama a la API."""


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _get_usage(db: Session, period: str) -> ApiUsage:
    usage = db.execute(
        select(ApiUsage).where(ApiUsage.source == SOURCE, ApiUsage.period == period)
    ).scalar_one_or_none()
    if usage is None:
        usage = ApiUsage(source=SOURCE, period=period, credits_used=0)
        db.add(usage)
        db.flush()
    return usage


def remaining_budget(db: Session) -> int:
    usage = _get_usage(db, _current_period())
    return settings.odds_monthly_budget - usage.credits_used


# --- normalización de mercados --------------------------------------------

def _normalize_outcome(market_key: str, name: str, point, home: str, away: str):
    """(market_key, outcome_name, point) → (market_norm, outcome_norm) o None si no soportado."""
    if market_key == "h2h":
        if name == home:
            return "1x2", "home"
        if name == away:
            return "1x2", "away"
        if name.lower() == "draw":
            return "1x2", "draw"
        return None
    if market_key == "totals" and point is not None:
        side = "over" if name.lower().startswith("over") else "under"
        return "over_under", f"{side}_{point}"
    if market_key == "spreads" and point is not None:
        side = "home" if name == home else "away"
        return "asian_handicap", f"{side}_{point}"
    return None


def _default_http_get(url: str, params: dict) -> list:
    import httpx

    resp = httpx.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


class OddsApiClient:
    def __init__(self, http_get=None, rate_limiter: RateLimiter | None = None):
        self._http_get = http_get or _default_http_get
        self._limiter = rate_limiter or RateLimiter(max_calls=5, per_seconds=60.0)

    def _credit_cost(self) -> int:
        markets = [m for m in settings.odds_markets.split(",") if m]
        regions = [r for r in settings.odds_region.split(",") if r]
        return max(1, len(markets) * len(regions))

    def fetch_odds(self, db: Session) -> list:
        """Devuelve los eventos con cuotas (cacheado). Gasta crédito solo en miss de caché."""
        url = f"{settings.odds_api_base_url}/sports/{settings.odds_sport}/odds"
        cache_key = f"{SOURCE}:{settings.odds_sport}:{settings.odds_region}:{settings.odds_markets}"
        cost = self._credit_cost()

        def fetcher() -> dict:
            period = _current_period()
            usage = _get_usage(db, period)
            if usage.credits_used + cost > settings.odds_monthly_budget:
                raise OddsBudgetError(
                    f"Presupuesto agotado: {usage.credits_used}/{settings.odds_monthly_budget}"
                )
            self._limiter.acquire()
            params = {
                "apiKey": settings.odds_api_key,
                "regions": settings.odds_region,
                "markets": settings.odds_markets,
                "oddsFormat": "decimal",
            }
            data = self._http_get(url, params)
            usage.credits_used += cost
            usage.updated_at = datetime.now(timezone.utc)
            return {"events": data}

        return cached_get(db, SOURCE, cache_key, ODDS_TTL, fetcher)["events"]

    def ingest_odds(self, db: Session) -> dict:
        """Mapea eventos→matches, normaliza y hace upsert en `odds`. Idempotente (precio actual)."""
        if not settings.odds_api_key:
            return {"skipped": "no_api_key", "events": 0, "rows": 0}

        events = self.fetch_odds(db)

        # Índice (home_name, away_name) → match (de nuestros partidos).
        teams_by_id = {t.id: t for t in db.execute(select(Team)).scalars().all()}
        match_index: dict[tuple[str, str], Match] = {}
        for m in db.execute(select(Match)).scalars().all():
            h = teams_by_id.get(m.home_id)
            a = teams_by_id.get(m.away_id)
            if h and a:
                match_index[(h.name, a.name)] = m

        matched_events = 0
        rows = 0
        for ev in events:
            home, away = ev.get("home_team"), ev.get("away_team")
            match = match_index.get((home, away))
            if match is None:
                continue
            matched_events += 1
            for book in ev.get("bookmakers", []):
                bk = book.get("key") or book.get("title", "?")
                for market in book.get("markets", []):
                    mk = market.get("key")
                    for oc in market.get("outcomes", []):
                        norm = _normalize_outcome(mk, oc.get("name", ""), oc.get("point"), home, away)
                        if norm is None:
                            continue
                        market_norm, outcome_norm = norm
                        rows += self._upsert_odds(
                            db, match.id, bk, market_norm, outcome_norm, float(oc["price"])
                        )
        db.commit()
        return {"events": matched_events, "rows": rows}

    @staticmethod
    def _upsert_odds(db, match_id, bookmaker, market, outcome, price) -> int:
        existing = db.execute(
            select(Odds).where(
                Odds.match_id == match_id, Odds.bookmaker == bookmaker,
                Odds.market == market, Odds.outcome == outcome,
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(Odds(match_id=match_id, bookmaker=bookmaker, market=market,
                        outcome=outcome, price=price, captured_at=datetime.now(timezone.utc)))
            return 1
        existing.price = price
        existing.captured_at = datetime.now(timezone.utc)
        return 0


def main() -> int:
    init_db()
    if not settings.odds_api_key:
        print("Falta ODDS_API_KEY en .env; no se llama a The Odds API.")
        return 1
    client = OddsApiClient()
    with SessionLocal() as db:
        summary = client.ingest_odds(db)
        rem = remaining_budget(db)
    print(f"Odds ingeridas: {summary} | créditos restantes este mes: {rem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
