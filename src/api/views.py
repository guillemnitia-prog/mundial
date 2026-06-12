"""Endpoints de lectura para la PWA (SPEC §7): lista de partidos, detalle, ranking, saldo.

Solo lectura sobre las tablas existentes. La generación de `predictions` la hace el scheduler
(Fase 12); aquí se muestran los datos que existan (estados pendiente / sin apuesta si no hay).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, require_onboarded
from src.bankroll import balance as balance_ops
from src.bankroll import kelly
from src.bankroll.balance import BalanceError
from src.db.schema import Bet, Match, Prediction, Team, User
from src.db.session import get_db

router = APIRouter(tags=["views"])

RECENT_FORM_N = 5


def display_state(match: Match) -> str:
    """Estado de ciclo de vida visible (SPEC §11)."""
    if match.status == "finished":
        return "finalizado"
    if match.status == "live":
        return "en vivo"
    if match.analysis_status == "analyzed":
        return "analizado"
    return "pendiente"


# --- modelos de salida -----------------------------------------------------

class MatchListItem(BaseModel):
    id: int
    utc_date: str | None
    stage: str
    group_label: str | None
    state: str
    status: str
    home: str | None
    away: str | None
    home_code: str | None
    away_code: str | None
    home_goals: int | None
    away_goals: int | None
    n_picks: int


class TeamInfo(BaseModel):
    name: str
    fifa_code: str | None
    elo: float | None
    is_host: bool


class PickOut(BaseModel):
    prediction_id: int
    market: str
    outcome: str
    model_prob: float
    fair_prob: float
    offered_odds: float
    ev_pct: float
    confidence: str | None
    stake_eur: float
    stake_pct: float
    too_small: bool
    your_decision: str | None


class MatchDetail(BaseModel):
    id: int
    utc_date: str | None
    stage: str
    group_label: str | None
    state: str
    status: str
    neutral_venue: bool
    home_goals: int | None
    away_goals: int | None
    analyzed_at: str | None
    analysis_stage: str | None
    home: TeamInfo | None
    away: TeamInfo | None
    home_form: list[str]
    away_form: list[str]
    picks: list[PickOut]
    message: str | None  # "Sin apuesta de valor en este partido" si no hay picks
    odds_proxy_notice: str


def _team_info(t: Team | None) -> TeamInfo | None:
    if t is None:
        return None
    return TeamInfo(name=t.name, fifa_code=t.fifa_code, elo=t.elo, is_host=t.is_host)


def _recent_form(db: Session, team_id: int) -> list[str]:
    """Últimos N resultados finalizados del equipo (W/D/L), más reciente primero."""
    rows = db.execute(
        select(Match).where(
            Match.status == "finished",
            (Match.home_id == team_id) | (Match.away_id == team_id),
        ).order_by(Match.utc_date.desc()).limit(RECENT_FORM_N)
    ).scalars().all()
    form: list[str] = []
    for m in rows:
        if m.home_goals is None or m.away_goals is None:
            continue
        is_home = m.home_id == team_id
        gf, ga = (m.home_goals, m.away_goals) if is_home else (m.away_goals, m.home_goals)
        form.append("W" if gf > ga else ("L" if gf < ga else "D"))
    return form


@router.get("/matches", response_model=list[MatchListItem])
def list_matches(_user: User = Depends(require_onboarded), db: Session = Depends(get_db)):
    matches = db.execute(select(Match).order_by(Match.utc_date)).scalars().all()
    teams = {t.id: t for t in db.execute(select(Team)).scalars().all()}
    pick_counts = {
        mid: n for mid, n in db.execute(
            select(Prediction.match_id, func.count(Prediction.id)).group_by(Prediction.match_id)
        ).all()
    }
    out = []
    for m in matches:
        h = teams.get(m.home_id)
        a = teams.get(m.away_id)
        out.append(MatchListItem(
            id=m.id, utc_date=m.utc_date.isoformat() if m.utc_date else None,
            stage=m.stage, group_label=m.group_label, state=display_state(m), status=m.status,
            home=h.name if h else None, away=a.name if a else None,
            home_code=h.fifa_code if h else None, away_code=a.fifa_code if a else None,
            home_goals=m.home_goals, away_goals=m.away_goals,
            n_picks=pick_counts.get(m.id, 0),
        ))
    return out


@router.get("/matches/{match_id}", response_model=MatchDetail)
def match_detail(match_id: int, current_user: User = Depends(require_onboarded),
                 db: Session = Depends(get_db)):
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="match_not_found")

    home = db.get(Team, m.home_id) if m.home_id else None
    away = db.get(Team, m.away_id) if m.away_id else None

    preds = db.execute(
        select(Prediction).where(Prediction.match_id == match_id).order_by(Prediction.rank)
    ).scalars().all()

    # Decisiones del usuario sobre estas predicciones.
    decisions = {
        b.prediction_id: b.decision for b in db.execute(
            select(Bet).where(Bet.user_id == current_user.id, Bet.match_id == match_id)
        ).scalars().all()
    }

    picks: list[PickOut] = []
    for p in preds:
        stake = kelly.user_stake(current_user.balance, p.recommended_stake or 0.0)
        picks.append(PickOut(
            prediction_id=p.id, market=p.market, outcome=p.outcome,
            model_prob=p.model_prob, fair_prob=p.fair_prob, offered_odds=p.offered_odds,
            ev_pct=round(p.ev * 100, 1), confidence=p.confidence,
            stake_eur=stake["eur"], stake_pct=round(stake["pct"] * 100, 1),
            too_small=stake["too_small"], your_decision=decisions.get(p.id),
        ))

    message = None if picks else "Sin apuesta de valor en este partido"
    return MatchDetail(
        id=m.id, utc_date=m.utc_date.isoformat() if m.utc_date else None,
        stage=m.stage, group_label=m.group_label, state=display_state(m), status=m.status,
        neutral_venue=m.neutral_venue,
        home_goals=m.home_goals, away_goals=m.away_goals,
        analyzed_at=m.analyzed_at.isoformat() if m.analyzed_at else None,
        analysis_stage=m.analysis_stage,
        home=_team_info(home), away=_team_info(away),
        home_form=_recent_form(db, m.home_id) if m.home_id else [],
        away_form=_recent_form(db, m.away_id) if m.away_id else [],
        picks=picks, message=message,
        odds_proxy_notice="Cuotas region=eu como proxy de Bet365.es/Sportium; pueden diferir.",
    )


class RankingRow(BaseModel):
    username: str
    balance: float


@router.get("/ranking", response_model=list[RankingRow])
def ranking(_user: User = Depends(require_onboarded), db: Session = Depends(get_db)):
    users = db.execute(select(User).order_by(User.balance.desc())).scalars().all()
    return [RankingRow(username=u.username, balance=round(u.balance, 2)) for u in users]


class BalanceSummary(BaseModel):
    balance: float
    n_bets: int
    n_open: int
    n_won: int
    n_lost: int
    total_pnl: float


class AmountIn(BaseModel):
    amount: float


_BALANCE_ERR = {"invalid_amount": 422, "insufficient_funds": 422, "amount_too_large": 422}


def _balance_op(op, current_user, db, value) -> dict:
    try:
        op(db, current_user, value)
    except BalanceError as exc:
        raise HTTPException(status_code=_BALANCE_ERR.get(exc.code, 400), detail=exc.code)
    return {"balance": round(current_user.balance, 2)}


@router.post("/me/balance/deposit")
def deposit(payload: AmountIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ingresar saldo."""
    return _balance_op(balance_ops.deposit, current_user, db, payload.amount)


@router.post("/me/balance/withdraw")
def withdraw(payload: AmountIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retirar saldo (no más que el disponible)."""
    return _balance_op(balance_ops.withdraw, current_user, db, payload.amount)


@router.post("/me/balance/set")
def set_balance(payload: AmountIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Fijar el saldo a un valor concreto (≥0)."""
    return _balance_op(balance_ops.set_balance, current_user, db, payload.amount)


@router.get("/me/balance", response_model=BalanceSummary)
def my_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    bets = db.execute(select(Bet).where(Bet.user_id == current_user.id)).scalars().all()
    settled = [b for b in bets if b.pnl is not None]
    return BalanceSummary(
        balance=round(current_user.balance, 2),
        n_bets=len([b for b in bets if b.decision != "rejected"]),
        n_open=len([b for b in bets if b.status == "open"]),
        n_won=len([b for b in bets if b.status == "won"]),
        n_lost=len([b for b in bets if b.status == "lost"]),
        total_pnl=round(sum(b.pnl for b in settled), 2),
    )
