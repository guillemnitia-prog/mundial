"""Primitivas de seguridad: hashing de contraseñas (argon2) y JWT.

Funciones puras, sin acceso a base de datos. Las contraseñas NUNCA se guardan en texto plano.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import settings

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Devuelve el hash argon2 de la contraseña."""
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Comprueba una contraseña contra su hash argon2."""
    try:
        return _pwd_context.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    """Genera un JWT firmado con `sub = subject` (username) y expiración.

    Usa el secreto/algoritmo/expiración de `settings`.
    """
    minutes = expires_minutes if expires_minutes is not None else settings.jwt_expire_minutes
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decodifica y valida un JWT. Devuelve el payload o None si es inválido/expirado."""
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
