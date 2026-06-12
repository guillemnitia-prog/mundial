"""Programador (APScheduler) que dispara las dos pasadas (SPEC §11.2).

- daily_refresh: una vez por la mañana (pasada preliminary).
- pre_match_refresh: periódico (cada 30 min) para coger ventanas ~2h/~1h antes de cada partido.

Ejecutar: python -m src.scheduler.runner
"""

from __future__ import annotations

from src.db.session import SessionLocal, init_db


def _run_daily():
    from src.ingest.elo import ingest_elo
    from src.ingest.football_data import FootballDataClient
    from src.ingest.odds_api import OddsApiClient
    from src.scheduler.daily_refresh import run

    with SessionLocal() as db:
        run(db, fd_client=FootballDataClient(), elo_ingest=ingest_elo, odds_client=OddsApiClient())


def _run_pre_match():
    from src.ingest.odds_api import OddsApiClient
    from src.scheduler.pre_match_refresh import run

    with SessionLocal() as db:
        run(db, odds_client=OddsApiClient())


def main() -> int:
    from apscheduler.schedulers.blocking import BlockingScheduler

    init_db()
    sched = BlockingScheduler(timezone="UTC")
    # Pasada de la mañana a las 08:00 UTC.
    sched.add_job(_run_daily, "cron", hour=8, minute=0, id="daily_refresh")
    # Pasada pre-partido cada 30 min.
    sched.add_job(_run_pre_match, "interval", minutes=30, id="pre_match_refresh")
    print("Scheduler iniciado (Ctrl+C para parar).")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
