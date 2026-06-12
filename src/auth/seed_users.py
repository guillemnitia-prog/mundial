"""Crea las 7 cuentas fijas (1 admin + 6 members). Ejecutar una vez.

    python -m src.auth.seed_users [--reset] [--file users_seed.json]

Las credenciales se leen de un fichero JSON local NO versionado (por defecto `users_seed.json`
en la raíz del repo) o de la variable de entorno `USERS_SEED_JSON`. Formato:

    [
      {"username": "admin",  "password": "...", "role": "admin"},
      {"username": "amigo1", "password": "...", "role": "member"},
      ...
    ]

Idempotente: omite los usuarios que ya existen. Con `--reset` re-hashea su contraseña.
NUNCA se commitea el fichero real (patrón `users_seed.*` en .gitignore).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from src.auth.users import create_user, get_user_by_username, reset_password
from src.config import BASE_DIR
from src.db.session import SessionLocal, init_db

DEFAULT_SEED_FILE = BASE_DIR / "users_seed.json"


def _load_seed(file_path: Path | None) -> list[dict]:
    """Carga las credenciales del fichero indicado o de USERS_SEED_JSON."""
    env_json = os.getenv("USERS_SEED_JSON")
    if env_json:
        data = json.loads(env_json)
    else:
        path = file_path or DEFAULT_SEED_FILE
        if not path.exists():
            raise FileNotFoundError(
                f"No se encontró {path}. Copia users_seed.example.json a users_seed.json "
                "y rellena las credenciales (no se versiona)."
            )
        data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, list) or not data:
        raise ValueError("El seed debe ser una lista no vacía de objetos {username,password,role}.")
    return data


def seed_users(entries: list[dict], reset: bool = False) -> dict:
    """Crea/actualiza usuarios. Devuelve un resumen {created, skipped, reset}."""
    init_db()
    summary = {"created": 0, "skipped": 0, "reset": 0}
    with SessionLocal() as db:
        for entry in entries:
            username = entry["username"]
            password = entry["password"]
            role = entry.get("role", "member")

            existing = get_user_by_username(db, username)
            if existing is None:
                create_user(db, username=username, password=password, role=role)
                summary["created"] += 1
            elif reset:
                reset_password(db, username=username, new_password=password)
                summary["reset"] += 1
            else:
                summary["skipped"] += 1
        db.commit()
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Crear las 7 cuentas fijas (idempotente).")
    parser.add_argument("--reset", action="store_true", help="re-hashear contraseñas de usuarios existentes")
    parser.add_argument("--file", type=Path, default=None, help="ruta del JSON de credenciales")
    args = parser.parse_args(argv)

    try:
        entries = _load_seed(args.file)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    summary = seed_users(entries, reset=args.reset)
    print(
        f"Seed completado: {summary['created']} creados, "
        f"{summary['reset']} reseteados, {summary['skipped']} omitidos."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
