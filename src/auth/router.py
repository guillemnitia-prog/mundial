"""Endpoints de autenticación (API JSON).

POST /auth/login, POST /auth/logout, GET /auth/me, POST /auth/admin/reset-password.
El JWT viaja en una cookie httpOnly (no se devuelve en el cuerpo).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user, require_admin
from src.auth.security import create_access_token
from src.auth.users import authenticate_user, reset_password
from src.config import settings
from src.db.schema import User
from src.db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    username: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    has_onboarded: bool
    balance: float

    @classmethod
    def from_user(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            role=user.role,
            has_onboarded=user.has_onboarded,
            balance=user.balance,
        )


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> UserOut:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
        )
    token = create_access_token(subject=user.username)
    _set_auth_cookie(response, token)
    return UserOut.from_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    response.delete_cookie(key=settings.cookie_name, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(current_user)


@router.post("/admin/reset-password", response_model=UserOut)
def admin_reset_password(
    payload: ResetPasswordRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserOut:
    user = reset_password(db, payload.username, payload.new_password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")
    db.commit()
    return UserOut.from_user(user)
