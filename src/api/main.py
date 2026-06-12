"""Aplicación FastAPI (API JSON pura). Crece en fases posteriores.

Por ahora monta los routers de auth y onboarding, configura CORS con credenciales para la PWA
Next.js e inicializa la base de datos al arrancar.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.bets import router as bets_router
from src.auth.onboarding import router as onboarding_router
from src.auth.router import router as auth_router
from src.api.push import router as push_router
from src.api.views import router as views_router
from src.chat.routes import router as chat_router
from src.config import settings
from src.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="WorldCup Betting Analyzer", lifespan=lifespan)

    # CORS con credenciales para la PWA (cookie httpOnly).
    # Permite el FRONTEND_ORIGIN configurado y CUALQUIER despliegue *.vercel.app
    # (evita tener que clavar la URL exacta de Vercel, que cambia entre despliegues).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(onboarding_router)
    app.include_router(bets_router)
    app.include_router(chat_router)
    app.include_router(views_router)
    app.include_router(push_router)

    @app.get("/health", tags=["meta"])
    def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
