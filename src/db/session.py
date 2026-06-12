"""Motor, sesiones e inicialización de la base de datos SQLite.

- `engine`: construido desde `settings.database_url`.
- Listener `PRAGMA foreign_keys=ON`: SQLite NO fuerza claves foráneas por defecto.
- `get_db()`: dependencia generadora para FastAPI.
- `init_db()`: crea la carpeta de datos y todas las tablas (`create_all`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import BASE_DIR, settings
from src.db.schema import Base


def _connect_args(database_url: str) -> dict:
    # check_same_thread=False permite usar la conexión entre hilos (uvicorn workers).
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


engine: Engine = create_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args=_connect_args(settings.database_url),
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
    """Activa la verificación de FK en cada conexión SQLite."""
    # Solo aplica al driver de SQLite (sqlite3 expone .execute en el cursor).
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # Otros backends no necesitan este PRAGMA.
        pass


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def _sqlite_path(database_url: str) -> Path | None:
    """Devuelve la ruta del fichero .db para una URL sqlite:///... (None si :memory: u otro)."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    rel = database_url[len(prefix):]
    if rel in ("", ":memory:"):
        return None
    path = Path(rel)
    return path if path.is_absolute() else (BASE_DIR / path)


def init_db() -> None:
    """Crea la carpeta de datos (si aplica) y todas las tablas."""
    db_path = _sqlite_path(settings.database_url)
    if db_path is not None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """Dependencia FastAPI: cede una sesión y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada en: {settings.database_url}")
