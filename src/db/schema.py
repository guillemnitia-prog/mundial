"""Esquema SQLite de WorldCup Betting Analyzer (SPEC §2).

Modelo de datos completo en SQLAlchemy ORM 2.0. Refleja las aclaraciones de dominio:
- Saldo virtual INDIVIDUAL por usuario (`users.balance`, 50 € de partida). NO hay bote común.
- `bets` por usuario (con `prediction_id`, `status`, `settled_at`).
- `balance_ledger` registra cada movimiento de saldo (la antigua tabla `bankroll` no existe).

Sin lógica de negocio: solo definición de tablas. La inicialización vive en `session.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Timestamp UTC con tzinfo (evita ambigüedades de zona horaria)."""
    return datetime.now(timezone.utc)


# Valores permitidos (se materializan como CHECK constraints en SQLite).
MATCH_STAGES = ("group", "R32", "R16", "QF", "SF", "3RD", "F")
MATCH_STATUSES = ("scheduled", "live", "finished", "postponed", "cancelled")
ANALYSIS_STATUSES = ("pending", "analyzed")  # el análisis se genera el día del partido
CONFIDENCE_LEVELS = ("alta", "media")        # nivel de confianza de una recomendación
USER_ROLES = ("admin", "member")
BET_STATUSES = ("open", "won", "lost", "void")

INITIAL_USER_BALANCE = 50.0  # € virtuales de partida por usuario (SPEC §5)


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)  # id football-data
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    fifa_code: Mapped[str | None] = mapped_column(String, index=True)
    elo: Mapped[float | None] = mapped_column(Float)  # Elo de eloratings.net (selecciones)
    confederation: Mapped[str | None] = mapped_column(String)
    is_host: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Ventaja local SOLO para anfitriones (USA/Canadá/México); el resto, campo neutral.


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int | None] = mapped_column(Integer, unique=True, index=True)  # id football-data
    utc_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Nullable: las eliminatorias aún sin definir no tienen rivales (no se analizan hasta confirmarse).
    home_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    away_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"))
    group_label: Mapped[str | None] = mapped_column(String)  # A..L (fase de grupos)
    stage: Mapped[str] = mapped_column(String, nullable=False, default="group")
    neutral_venue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    home_goals: Mapped[int | None] = mapped_column(Integer)
    away_goals: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")

    # Ciclo de vida del análisis (el análisis se genera el DÍA del partido, no antes).
    # Estado visible UI = derivado de (status, analysis_status): pendiente → analizado → en vivo → finalizado.
    analysis_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending|analyzed
    analysis_stage: Mapped[str | None] = mapped_column(String)  # preliminary|final (qué pasada lo generó)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # "Actualizado hace X min"

    home_team: Mapped["Team"] = relationship("Team", foreign_keys=[home_id])
    away_team: Mapped["Team"] = relationship("Team", foreign_keys=[away_id])

    __table_args__ = (
        CheckConstraint(f"stage IN {MATCH_STAGES}", name="ck_matches_stage"),
        CheckConstraint(f"status IN {MATCH_STATUSES}", name="ck_matches_status"),
        CheckConstraint(f"analysis_status IN {ANALYSIS_STATUSES}", name="ck_matches_analysis_status"),
    )


class Odds(Base):
    __tablename__ = "odds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    bookmaker: Mapped[str] = mapped_column(String, nullable=False)
    market: Mapped[str] = mapped_column(String, nullable=False)  # h2h, totals, spreads, btts...
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)  # cuota decimal
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    model_prob: Mapped[float] = mapped_column(Float, nullable=False)
    fair_prob: Mapped[float] = mapped_column(Float, nullable=False)  # prob del bookie sin margen
    offered_odds: Mapped[float] = mapped_column(Float, nullable=False)
    ev: Mapped[float] = mapped_column(Float, nullable=False)
    # Fracción recomendada de ¼ Kelly (% del saldo), INDEPENDIENTE del usuario.
    # El importe en € se calcula por usuario sobre su saldo en bankroll/kelly.py (Fase 9).
    recommended_stake: Mapped[float | None] = mapped_column(Float)
    rank: Mapped[int | None] = mapped_column(Integer)  # 1 o 2 (los 2 de mayor EV)
    # Nivel de confianza (alta|media) según model_prob y margen de EV. Solo se guardan
    # recomendaciones que cumplen model_prob >= MIN_CONFIDENCE y EV>0 y cuota>=1.40 (value/ev.py).
    confidence: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)  # argon2, nunca texto plano
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    has_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Saldo virtual individual (NO bote común): 50 € de partida por usuario.
    balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=INITIAL_USER_BALANCE, server_default=str(INITIAL_USER_BALANCE)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (CheckConstraint(f"role IN {USER_ROLES}", name="ck_users_role"),)


class ChampionPick(Base):
    __tablename__ = "champion_picks"

    # PK en user_id → un único pick por usuario, inmutable una vez creado.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"))
    market: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    stake: Mapped[float] = mapped_column(Float, nullable=False)  # € apostados (sobre su saldo)
    odds: Mapped[float] = mapped_column(Float, nullable=False)   # cuota tomada
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    result: Mapped[str | None] = mapped_column(String)
    pnl: Mapped[float | None] = mapped_column(Float)
    clv: Mapped[float | None] = mapped_column(Float)  # cuota apostada vs cierre
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (CheckConstraint(f"status IN {BET_STATUSES}", name="ck_bets_status"),)


class BalanceLedger(Base):
    __tablename__ = "balance_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    bet_id: Mapped[int | None] = mapped_column(ForeignKey("bets.id"))
    delta: Mapped[float] = mapped_column(Float, nullable=False)         # +/- aplicado al saldo
    balance_after: Mapped[float] = mapped_column(Float, nullable=False)  # saldo resultante
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class ApiCache(Base):
    """Caché de respuestas HTTP crudas (SPEC §1: cachear TODO, nunca llamar en cada request).

    Reutilizable por todos los clientes de ingest. `cache_key` identifica unívocamente la petición
    (source + path + params); `expires_at` controla el TTL.
    """

    __tablename__ = "api_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String, nullable=False)  # p.ej. "football-data"
    cache_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    response_json: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
