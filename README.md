# WorldCup Betting Analyzer

App privada de análisis de **value betting** para el Mundial FIFA 2026, para un grupo de 7
amigos. Para cada partido produce un análisis detallado y **2 pronósticos honestos** (solo con
EV > 0 y cuota decimal ≥ 1,40), con stake sugerido por **Kelly fraccionado (1/4)**. El modelo
estadístico (ensemble Dixon-Coles + Elo) vive dentro de la app.

Lee `SPEC.md` (especificación), `CLAUDE.md` (reglas operativas) y `DECISIONS.md`
(decisiones técnicas de la Fase 0) antes de tocar nada.

## Stack
Python 3.11 · FastAPI · SQLite · numpy/scipy/pandas · APScheduler · Jinja2 + HTMX · pytest

## Puesta en marcha
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # y rellena tokens y JWT_SECRET (openssl rand -hex 32)
```

## Comandos
- `uvicorn src.api.main:app --reload` → dev server
- `python -m src.scheduler.daily_refresh` → refresco diario de datos (cron)
- `python -m src.models.ensemble --train` → reentrenar el modelo
- `python -m src.auth.seed_users` → crear las 7 cuentas (ejecutar 1 vez)
- `pytest` → tests

## Estado
App completa (modelo, value betting, saldos, decisión/deshacer, chat, PWA, scheduler, push).
Frontend en `frontend/` (Next.js PWA). Para publicarla, ver **DEPLOY.md** (Render + Vercel).

## ⚠️ Juego responsable
Solo +18. Apostar conlleva **riesgo real de pérdida**; batir al mercado a largo plazo es muy
difícil. Esto es una herramienta de **análisis y entretenimiento**, no una inversión garantizada.
Límites legales DGOJ: 600 €/día, 1.500 €/semana, 3.000 €/mes. No se juega a crédito.
Ayuda y autoexclusión: [jugarbien.es](https://www.jugarbien.es) · FEJAR · RGIAJ / app *Stop Juego*.
