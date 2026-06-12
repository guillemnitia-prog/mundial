"""Pasada de la mañana (SPEC §11.2): refresco de datos + liquidación + análisis preliminar + push.

Ciclo diario:
1. Ingesta de football-data (resultados + fixtures) y Elo (cacheado).
2. Ingesta de odds (con presupuesto de créditos; sin ODDS_API_KEY se omite).
3. Transiciones de ciclo de vida: lock de partidos en vivo + liquidación de finalizados.
4. Notificaciones de liquidación (disparador; envío real en Fase 13).
5. Análisis PRELIMINAR de los partidos de HOY (escribe predictions).

Inyección de dependencias para testear sin red.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.schema import Match
from src.models.ensemble import EnsembleModel
from src.notifications import events as notify
from src.scheduler.analysis import analyze_match
from src.scheduler.lifecycle import transition_and_settle


def _today_matches(db: Session, today: date) -> list[Match]:
    rows = db.execute(select(Match).where(Match.utc_date.isnot(None))).scalars().all()
    return [m for m in rows if m.utc_date and m.utc_date.date() == today and m.status != "finished"]


def _load_ensemble() -> EnsembleModel | None:
    try:
        return EnsembleModel.load()
    except Exception:
        return None


def run(db: Session, *, now: datetime | None = None, fd_client=None, elo_ingest=None,
        odds_client=None, ensemble: EnsembleModel | None = None, ingest: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    summary: dict = {"ingested": False, "analyzed": 0, "push": 0}

    if ingest:
        try:
            if fd_client is not None:
                fd_client.refresh(db)
            if elo_ingest is not None:
                elo_ingest(db)
            if odds_client is not None:
                odds_client.ingest_odds(db)
            summary["ingested"] = True
        except Exception as exc:  # ingesta no debe tumbar el resto de la pasada
            summary["ingest_error"] = str(exc)

    # Ciclo de vida + liquidación.
    life = transition_and_settle(db)
    summary["defaults_materialized"] = life["defaults_materialized"]

    # Notificaciones de liquidación.
    payloads = [
        notify.settlement_message(db, e["user"], e["bet"], e["match"])
        for e in life["settlement_events"]
    ]
    summary["push"] = notify.dispatch(payloads, db)
    summary["settled"] = len(life["settlement_events"])

    # Análisis preliminar de los partidos de hoy.
    model = ensemble or _load_ensemble()
    if model is not None:
        for m in _today_matches(db, now.date()):
            analyze_match(db, m, model, stage="preliminary", now=now)
            summary["analyzed"] += 1
    else:
        summary["analysis_skipped"] = "sin modelo entrenado (data/model_params.json)"
    return summary


def main() -> int:
    from src.db.session import SessionLocal, init_db
    from src.ingest.elo import ingest_elo
    from src.ingest.football_data import FootballDataClient
    from src.ingest.odds_api import OddsApiClient

    init_db()
    with SessionLocal() as db:
        summary = run(
            db,
            fd_client=FootballDataClient(),
            elo_ingest=ingest_elo,
            odds_client=OddsApiClient(),
        )
    print(f"daily_refresh: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
