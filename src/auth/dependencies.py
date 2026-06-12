"""Dependencias de autenticación para FastAPI.

- `get_current_user`: lee el JWT de la cookie httpOnly y carga el usuario (401 si falta/!válido).
- `require_admin`: exige rol admin (403).
- `require_onboarded`: exige onboarding completado (403 `onboarding_required`).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.auth.security import decode_token
from src.auth.users import get_user_by_username
from src.config import settings
from src.db.schema import User
from src.db.session import get_db


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )
    payload = decode_token(token)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_token",
        )
    user = get_user_by_username(db, payload["sub"])
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="user_not_found",
        )
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin_required")
    return current_user


def require_onboarded(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.has_onboarded:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="onboarding_required",
        )
    return current_user
