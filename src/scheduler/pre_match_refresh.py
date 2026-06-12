"""Pasada final pre-partido (SPEC §11.2): ~2h y ~1h antes del pitido.

Para los partidos de hoy próximos al inicio: cuotas frescas + (opcional) alineaciones/lesiones
(API-Football, stub si no hay key) → re-análisis FINAL → push "1 hora antes" con la recomendación.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.schema import Match
from src.models.ensemble import EnsembleModel
from src.notifications import events as notify
from src.scheduler.analysis import analyze_match
from src.scheduler.daily_refresh import _load_ensemble

# Ventana: partidos que empiezan dentro de las próximas WINDOW_HOURS.
WINDOW_HOURS = 2.5


def _upcoming(db: Session, now: datetime) -> list[Match]:
    horizon = now + timedelta(hours=WINDOW_HOURS)
    rows = db.execute(
        select(Match).where(Match.status == "scheduled", Match.utc_date.isnot(None))
    ).scalars().all()
    return [m for m in rows if m.utc_date and now <= m.utc_date <= horizon]


def run(db: Session, *, now: datetime | None = None, odds_client=None,
        ensemble: EnsembleModel | None = None, ingest: bool = True) -> dict:
    now = now or datetime.now(timezone.utc)
    summary = {"reanalyzed": 0, "push": 0}

    if ingest and odds_client is not None:
        try:
            odds_client.ingest_odds(db)
        except Exception as exc:
            summary["ingest_error"] = str(exc)

    model = ensemble or _load_ensemble()
    if model is None:
        summary["analysis_skipped"] = "sin modelo entrenado"
        return summary

    payloads = []
    for m in _upcoming(db, now):
        picks = analyze_match(db, m, model, stage="final", now=now)
        summary["reanalyzed"] += 1
        # Push "1h antes" con el mejor pick (si lo hay). El € por usuario se personaliza al
        # enviar (Fase 13); aquí va el stake base sobre el saldo inicial de 50 €.
        if picks:
            from src.bankroll import kelly

            top = picks[0]
            frac = kelly.recommended_fraction(top["model_prob"], top["offered_odds"])
            payloads.append(
                notify.pre_match_message(db, m, top["outcome"], top["offered_odds"], round(50.0 * frac, 2))
            )
    summary["push"] = notify.dispatch(payloads, db)
    return summary


def main() -> int:
    from src.db.session import SessionLocal, init_db
    from src.ingest.odds_api import OddsApiClient

    init_db()
    with SessionLocal() as db:
        summary = run(db, odds_client=OddsApiClient())
    print(f"pre_match_refresh: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
