"""Operaciones de usuario sobre la base de datos (crear, autenticar, resetear).

Sin registro público: las cuentas las crea el admin vía `seed_users.py`. Aquí van las
operaciones reutilizadas por el router de auth y por el seeding.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.security import hash_password, verify_password
from src.db.schema import User

VALID_ROLES = ("admin", "member")


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.execute(select(User).where(User.username == username)).scalar_one_or_none()


def create_user(db: Session, username: str, password: str, role: str = "member") -> User:
    """Crea un usuario con contraseña hasheada (argon2). No hace commit."""
    if role not in VALID_ROLES:
        raise ValueError(f"Rol inválido: {role!r} (debe ser uno de {VALID_ROLES})")
    user = User(username=username, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()  # asigna id sin cerrar la transacción
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Devuelve el usuario si las credenciales son correctas; None en caso contrario."""
    user = get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def reset_password(db: Session, username: str, new_password: str) -> User | None:
    """Cambia la contraseña de un usuario (uso del admin). No hace commit."""
    user = get_user_by_username(db, username)
    if user is None:
        return None
    user.password_hash = hash_password(new_password)
    db.flush()
    return user
