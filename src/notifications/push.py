"""Envío real de Web Push con pywebpush (SPEC §10).

Busca suscripciones en `push_subscriptions`, envía el payload con claims VAPID y purga las
suscripciones expiradas (404/410). Sin VAPID_PRIVATE_KEY → no-op seguro (push desactivado).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import settings
from src.db.schema import PushSubscription

logger = logging.getLogger("notifications.push")


def push_enabled() -> bool:
    return bool(settings.vapid_private_key)


def _subscription_info(sub: PushSubscription) -> dict:
    return {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}


def _send_one(sub: PushSubscription, payload: dict, ttl: int = 3600) -> bool:
    """Envía a una suscripción. Devuelve True si sigue válida; False si hay que purgarla."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=_subscription_info(sub),
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
            ttl=ttl,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            return False  # suscripción expirada → purgar
        logger.warning("Fallo de push (no purgable): %s", exc)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error enviando push: %s", exc)
        return True


def _send_to_subs(db: Session, subs: list[PushSubscription], payload: dict) -> int:
    sent = 0
    for sub in subs:
        ok = _send_one(sub, payload)
        if ok:
            sent += 1
        else:
            db.delete(sub)  # purgar expirada
    db.commit()
    return sent


def send_to_user(db: Session, user_id: int, payload: dict) -> int:
    if not push_enabled():
        logger.info("Push desactivado (sin VAPID): %s", payload.get("title"))
        return 0
    subs = db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    ).scalars().all()
    return _send_to_subs(db, subs, payload)


def send_to_all(db: Session, payload: dict) -> int:
    if not push_enabled():
        logger.info("Push desactivado (sin VAPID): %s", payload.get("title"))
        return 0
    subs = db.execute(select(PushSubscription)).scalars().all()
    return _send_to_subs(db, subs, payload)


def generate_vapid_keys() -> dict:
    """Genera un par de claves VAPID (application server keys) para pegar en .env."""
    from py_vapid import Vapid

    v = Vapid()
    v.generate_keys()
    # Claves en formato base64url para Web Push.
    return {
        "public_key": v.public_key_urlsafe_base64() if hasattr(v, "public_key_urlsafe_base64") else _pub_b64(v),
        "private_key": v.private_key_urlsafe_base64() if hasattr(v, "private_key_urlsafe_base64") else _priv_b64(v),
    }


def _pub_b64(v) -> str:
    import base64
    from cryptography.hazmat.primitives import serialization

    raw = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _priv_b64(v) -> str:
    import base64

    raw = v.private_key.private_numbers().private_value.to_bytes(32, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Utilidades de Web Push.")
    parser.add_argument("--generate-keys", action="store_true", help="generar par VAPID")
    args = parser.parse_args(argv)
    if args.generate_keys:
        keys = generate_vapid_keys()
        print("Pega esto en tu .env (NO lo subas a git):\n")
        print(f"VAPID_PUBLIC_KEY={keys['public_key']}")
        print(f"VAPID_PRIVATE_KEY={keys['private_key']}")
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
