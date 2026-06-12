# DEPLOY.md — publicar la PWA (Render + Vercel)

Objetivo: que tus amigos la instalen en el móvil por **HTTPS** (requisito de PWA y de push en iOS).
Backend FastAPI en **Render**, frontend Next.js en **Vercel**. Todo gratis/barato para 7 personas.

## 0. Antes de empezar (local, una vez)
1. **Claves VAPID** (push): `python -m src.notifications.push --generate-keys` → guarda las dos.
2. **ODDS_API_KEY**: regístrate en https://the-odds-api.com (free 500/mes). Sin ella no hay picks.
3. **Cuentas**: edita `users_seed.json` (ya creado, gitignored) con las contraseñas reales de
   `guillem` (admin) y `marc` (member). Añade más amigos si quieres.

## 1. Base de datos en Supabase (gratis, persistente)
1. Crea un proyecto en https://supabase.com (free). Elige región europea.
2. **Project Settings → Database → Connection string → URI**. Copia la cadena
   (`postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres`). Esa es tu `DATABASE_URL`.
   (El backend normaliza `postgres://`→`postgresql+psycopg2://` automáticamente.)
3. No hay que crear tablas a mano: el backend las crea con `create_all` al arrancar.

## 2. Backend en Render (plan free)
1. En Render: **New → Blueprint** apuntando al repo (`render.yaml`), o **New → Web Service** (Docker).
2. Variables de entorno (`sync:false` en el blueprint):
   - `DATABASE_URL` = la URI de Supabase del paso 1.
   - `FOOTBALL_DATA_TOKEN`, `ODDS_API_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
     `VAPID_SUBJECT=mailto:tu@email`, `FRONTEND_ORIGIN=https://<tu-app>.vercel.app`.
   - `JWT_SECRET` se autogenera; `COOKIE_SECURE=true`, `COOKIE_SAMESITE=none` (cookies cross-site).
3. **Inicialización** (una vez, desde la Shell de Render; los datos van a Supabase y persisten):
   ```
   python -m src.auth.seed_users          # crea las cuentas (sube users_seed.json a la shell)
   python -m src.ingest.football_data     # equipos + partidos
   python -m src.ingest.elo               # Elo
   python -m src.models.ensemble --train  # entrena el modelo (data/model_params.json)
   ```
4. La API queda en `https://mundial-api.onrender.com` (verifica `/health`).
   Nota free: el servicio se duerme tras inactividad (1ª carga lenta) y **no hay cron** → la pasada
   diaria se lanza a mano (Shell) o con un cron externo (p.ej. cron-job.org) que llame a un endpoint.

## 3. Frontend en Vercel
1. En Vercel: **New Project** → el mismo repo, **Root Directory = `frontend`**.
2. Variable de entorno: `NEXT_PUBLIC_API_BASE=https://mundial-api.onrender.com`.
3. Deploy. Te da `https://<tu-app>.vercel.app` → pon ese valor en `FRONTEND_ORIGIN` del backend.
4. (Importante) Al cambiar `NEXT_PUBLIC_API_BASE` hay que **redeploy** del front.

## 4. Instalar en el móvil (tus amigos)
- iPhone (Safari): abrir la URL → Compartir → **Añadir a pantalla de inicio**. Push funciona desde
  **iOS 16.4** solo con la PWA instalada; el permiso se pide tras el onboarding.
- Android (Chrome): banner **Instalar app** / menú → Instalar.

## 5. Scheduler (análisis diario + liquidación + push)
- En el plan free de Render no hay cron. Lanza `python -m src.scheduler.daily_refresh` desde la
  Shell, o configura un cron externo (cron-job.org / GitHub Actions) que lo dispare a diario.
- El modelo entrenado (`data/model_params.json`) es efímero en free: re-ejecuta `--train` tras cada
  redeploy (o súbelo a la imagen) para que haya picks.

## Notas
- **HTTPS obligatorio** para PWA/push: Render y Vercel lo dan automáticamente.
- **Cookies cross-site**: `COOKIE_SAMESITE=none` + `COOKIE_SECURE=true` + `FRONTEND_ORIGIN` exacto.
- **Datos en Supabase (Postgres)** = persistentes y gratis. SQLite queda solo para desarrollo local.
- Migraciones: el esquema se crea con `create_all`; ante cambios de esquema fuertes, considerar Alembic.
