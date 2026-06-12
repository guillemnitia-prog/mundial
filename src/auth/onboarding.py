"""Onboarding del campeón (API JSON).

Tras el primer login y ANTES de usar la app, cada usuario elige qué selección cree que ganará
el Mundial. El pick es INMUTABLE (un único pick por usuario, respaldado por la PK de
champion_picks) y, una vez enviado, marca `has_onboarded=true`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, require_onboarded
from src.db.schema import ChampionPick, Team, User
from src.db.session import get_db

router = APIRouter(tags=["onboarding"])


class TeamOut(BaseModel):
    id: int
    name: str
    fifa_code: str | None = None


class OnboardingStatus(BaseModel):
    has_onboarded: bool
    teams: list[TeamOut]  # selecciones disponibles para el selector (cargadas en Fase 4)


class ChampionPickRequest(BaseModel):
    team_id: int


class ChampionPickOut(BaseModel):
    user_id: int
    username: str
    team_id: int
    team_name: str


def _list_teams(db: Session) -> list[TeamOut]:
    teams = db.execute(select(Team).order_by(Team.name)).scalars().all()
    return [TeamOut(id=t.id, name=t.name, fifa_code=t.fifa_code) for t in teams]


@router.get("/onboarding", response_model=OnboardingStatus)
def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatus:
    return OnboardingStatus(has_onboarded=current_user.has_onboarded, teams=_list_teams(db))


@router.post("/onboarding/champion", response_model=ChampionPickOut, status_code=status.HTTP_201_CREATED)
def submit_champion(
    payload: ChampionPickRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChampionPickOut:
    # Inmutable: si ya tiene pick, no se permite cambiarlo.
    existing = db.get(ChampionPick, current_user.id)
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="champion_already_set")

    team = db.get(Team, payload.team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="team_not_found")

    db.add(ChampionPick(user_id=current_user.id, team_id=team.id))
    current_user.has_onboarded = True
    db.commit()
    return ChampionPickOut(
        user_id=current_user.id,
        username=current_user.username,
        team_id=team.id,
        team_name=team.name,
    )


@router.get("/champion-picks", response_model=list[ChampionPickOut])
def champion_picks(
    _user: User = Depends(require_onboarded),
    db: Session = Depends(get_db),
) -> list[ChampionPickOut]:
    rows = db.execute(
        select(ChampionPick, User, Team)
        .join(User, ChampionPick.user_id == User.id)
        .join(Team, ChampionPick.team_id == Team.id)
        .order_by(User.username)
    ).all()
    return [
        ChampionPickOut(user_id=u.id, username=u.username, team_id=t.id, team_name=t.name)
        for (_pick, u, t) in rows
    ]
