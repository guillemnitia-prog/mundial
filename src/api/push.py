"""Endpoints de Web Push (SPEC §7, §10)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.config import settings
from src.db.schema import PushSubscription, User
from src.db.session import get_db

router = APIRouter(prefix="/push", tags=["push"])


class SubscriptionKeys(BaseModel):
    p256dh: str
    auth: str


class SubscriptionIn(BaseModel):
    endpoint: str
    keys: SubscriptionKeys


@router.get("/vapid-public-key")
def vapid_public_key() -> dict:
    return {"key": settings.vapid_public_key}


@router.post("/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(
    payload: SubscriptionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    existing = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == payload.endpoint)
    ).scalar_one_or_none()
    if existing is None:
        db.add(PushSubscription(
            user_id=current_user.id, endpoint=payload.endpoint,
            p256dh=payload.keys.p256dh, auth=payload.keys.auth,
        ))
    else:
        # Reasignar al usuario actual y actualizar claves (mismo dispositivo).
        existing.user_id = current_user.id
        existing.p256dh = payload.keys.p256dh
        existing.auth = payload.keys.auth
    db.commit()
    return {"status": "subscribed"}


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    endpoint = payload.get("endpoint")
    if endpoint:
        sub = db.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == endpoint,
                PushSubscription.user_id == current_user.id,
            )
        ).scalar_one_or_none()
        if sub:
            db.delete(sub)
            db.commit()
    return None
