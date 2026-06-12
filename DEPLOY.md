# DEPLOY.md — publicar la PWA (Render + Vercel)

Objetivo: que tus amigos la instalen en el móvil por **HTTPS** (requisito de PWA y de push en iOS).
Backend FastAPI en **Render**, frontend Next.js en **Vercel**. Todo gratis/barato para 7 personas.

## 0. Antes de empezar (local, una vez)
1. **Claves VAPID** (push): `python -m src.notifications.push --generate-keys` → guarda las dos.
2. **ODDS_API_KEY**: regístrate en https://the-odds-api.com (free 500/mes). Sin ella no hay picks.
3. **Cuentas**: edita `users_seed.json` (ya creado, gitignored) con las contraseñas reales de
   `guillem` (admin) y `marc` (member). Añade más amigos si quieres.

## 1. Backend en Render
1. Sube el repo a GitHub (sin `.env` ni `users_seed.json`; ya están en .gitignore).
2. En Render: **New → Blueprint** y apunta al repo (usa `render.yaml`). Crea el servicio
   `mundial-api` (Docker) con disco persistente en `/app/data`.
3. Variables de entorno (Render → Environment), marcadas `sync:false` en el blueprint:
   - `FOOTBALL_DATA_TOKEN`, `ODDS_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
     `VAPID_SUBJECT=mailto:tu@email`, `FRONTEND_ORIGIN=https://<tu-app>.vercel.app`.
   - `JWT_SECRET` se autogenera; `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none` (cookies cross-site
     entre Vercel y Render), `DATABASE_URL=sqlite:////app/data/worldcup.db` (ya en el blueprint).
4. **Inicialización** (una vez, desde la Shell de Render del servicio, con el disco montado):
   ```
   python -m src.auth.seed_users          # crea las cuentas (lee users_seed.json — súbelo a la shell)
   python -m src.ingest.football_data     # equipos + partidos
   python -m src.ingest.elo               # Elo
   python -m src.models.ensemble --train  # entrena el modelo (data/model_params.json)
   ```
   (Alternativa: ejecuta esto en local y sube `data/worldcup.db` + `data/model_params.json` al disco.)
5. La API queda en `https://mundial-api.onrender.com` (verifica `/health`).

## 2. Frontend en Vercel
1. En Vercel: **New Project** → el mismo repo, **Root Directory = `frontend`**.
2. Variable de entorno: `NEXT_PUBLIC_API_BASE=https://mundial-api.onrender.com`.
3. Deploy. Te da `https://<tu-app>.vercel.app` → pon ese valor en `FRONTEND_ORIGIN` del backend.
4. (Importante) Al cambiar `NEXT_PUBLIC_API_BASE` hay que **redeploy** del front.

## 3. Instalar en el móvil (tus amigos)
- iPhone (Safari): abrir la URL → Compartir → **Añadir a pantalla de inicio**. Push funciona desde
  **iOS 16.4** solo con la PWA instalada; el permiso se pide tras el onboarding.
- Android (Chrome): banner **Instalar app** / menú → Instalar.

## 4. Scheduler (análisis diario + liquidación + push)
- El blueprint incluye un cron `mundial-daily` (08:00 UTC) que ejecuta `daily_refresh`. La pasada
  pre-partido (`pre_match_refresh`) puedes añadirla como otro cron cada 30 min, o disparar a mano.
- Cron y disco persistente en Render requieren plan de pago; en free puedes lanzar el refresco
  manualmente desde la Shell.

## Notas
- **HTTPS obligatorio** para PWA/push: Render y Vercel lo dan automáticamente.
- **Cookies cross-site**: `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true` + `FRONTEND_ORIGIN` exacto.
- **SQLite** sirve para 7 usuarios; si crece, migrar a Postgres (cambiar `DATABASE_URL`).
- Migraciones: el esquema se crea con `create_all`; ante cambios de esquema, regenerar la DB
  (sin Alembic todavía).
