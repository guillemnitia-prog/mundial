# Proyecto: WorldCup Betting Analyzer

App de análisis de apuestas para el Mundial FIFA 2026. Analiza cada partido en detalle,
produce 2 pronósticos por partido con **value betting honesto** (no "adivinar ganador"),
y los usa un grupo privado de 7 amigos. El modelo estadístico VIVE dentro de la app.

Lee SPEC.md para la especificación completa antes de implementar cualquier módulo.

## Stack
- Python 3.11, FastAPI, SQLite, scipy / numpy / pandas, APScheduler
- Auth: passlib[argon2] + python-jose (JWT) o cookies de sesión
- Chat: WebSockets nativos de FastAPI
- Frontend: **Next.js PWA (React + TS + Tailwind + Framer Motion)**, mobile-only. FastAPI = API
  JSON pura. Ver DESIGN.md (tokens, plataforma, 21st.dev Magic). [decidido en Fase 0 + brief visual]
- Tests: pytest

## Comandos
- `uvicorn src.api.main:app --reload`      → dev server
- `python -m src.scheduler.daily_refresh`  → refresco de datos (cron diario)
- `python -m src.models.ensemble --train`  → reentrenar modelo
- `python -m src.auth.seed_users`          → crear las 7 cuentas (ejecutar 1 vez)
- `pytest`                                 → tests

## Arquitectura (src/)
- ingest/   → clientes de APIs: football-data.org, The Odds API, eloratings (con caché)
- models/   → dixon_coles.py, elo_model.py, ensemble.py  (EL MODELO VIVE AQUÍ)
- value/    → devig.py (quita margen) + ev.py (detecta EV>0, filtra cuota >= 1.40)
- bankroll/ → kelly.py (1/4 Kelly sobre saldo individual) + settle.py (liquidación + balance_ledger)
- auth/     → users.py (hash/login), onboarding.py (pregunta campeón), seed_users.py
- chat/     → manager.py (ConnectionManager/broadcast) + routes.py (/ws/chat)
- db/       → schema.py (SQLite; users.balance, bets por usuario, balance_ledger)
- api/      → main.py (endpoints FastAPI)
- scheduler/→ daily_refresh.py

## Reglas de dominio (CRÍTICAS)
- El núcleo es VALUE BETTING: cada pronóstico compara prob del modelo vs prob justa del
  bookie (sin margen) y reporta EV. Nunca recomendar sin EV positivo.
- Modelo = ensemble Dixon-Coles (con time-decay) + Elo. Selecciones, no clubes:
  usa Elo de eloratings.net, NUNCA ClubElo.
- Ventaja local SOLO para anfitriones (USA/Canadá/México). Resto = campo neutral.
- Los 2 pronósticos por partido SOLO con cuota decimal >= 1.40. Filtrar en value/ev.py
  ANTES de elegir los 2 de mayor EV. Si quedan <2 con EV>0, mostrar los que haya (no inventar).
- Saldo VIRTUAL INDIVIDUAL: cada uno de los 7 usuarios empieza con 50 € (users.balance,
  DEFAULT 50.0). NO es un bote común: 7 saldos independientes. El stake en € se recalcula
  por usuario sobre su saldo ACTUAL, aunque el pronóstico (outcome+cuota) sea el mismo.
- Stake = 1/4 Kelly sobre el saldo del usuario (stake = saldo·(f/4)), nunca >5% del saldo.
  No apostar si EV<=0. Si el stake sale <1 € (o < mínimo de la casa): "demasiado pequeña,
  no apostar". Nunca todo el saldo en un partido. Devolver stake en € y en % del saldo.
- Cada usuario acepta ("apostar") o se salta ("saltar") cada recomendación; el saldo refleja
  solo lo apostado. Liquidación AUTOMÁTICA al terminar el partido (gana: balance+=stake·(odds−1);
  pierde: balance−=stake), registrando cada movimiento en balance_ledger. Ranking de grupo por saldo.
- Cachea TODO en SQLite. Respeta límites: football-data 10 req/min,
  The Odds API 500 créditos/mes. Nunca llamar APIs en cada request.
- Bet365.es/Sportium NO tienen API: usa cuotas region=eu como proxy y AVISA de la diferencia.
- The Odds API NO incluye Pinnacle; para la línea sharp usa OddsPapi o consenso eu.

## Usuarios y acceso
- 7 cuentas fijas creadas por el admin vía seed_users.py. NO hay registro público.
- Login usuario+contraseña; hash con argon2 (NUNCA texto plano).
- Sesión JWT httpOnly o cookie. Todas las rutas de la app protegidas tras login.
- Rol admin (1) puede resetear credenciales; members (6) solo acceden.

## Onboarding (primer acceso, OBLIGATORIO)
- Tras el primer login y ANTES de entrar a la app: "¿Qué equipo crees que ganará el Mundial?"
  con selector de las 48 selecciones. Respuesta obligatoria.
- Guardar en champion_picks. INMUTABLE una vez enviado. Marcar users.has_onboarded=true.
- En logins posteriores, saltar la pregunta. Los picks son visibles para todo el grupo.

## Chat en directo
- WebSocket en /ws/chat. ConnectionManager en memoria + broadcast a los conectados.
- Persistir en chat_messages; al conectar, cargar las últimas 50.
- Mostrar username + hora. Solo usuarios autenticados pueden conectar al socket.

## Prohibido
- No llamar APIs en cada request (usa la caché de SQLite).
- No prometer beneficios; incluir SIEMPRE disclaimers de juego responsable.
- No scrapear Bet365 (anti-bot + viola ToS).
- No commitear .env, API keys ni contraseñas.

## Juego responsable (mostrar visible en la app)
- Edad 18+. Riesgo real de pérdida.
- Límites legales DGOJ: 600 €/día, 1.500 €/semana, 3.000 €/mes. No se juega a crédito.
- Autoexclusión: RGIAJ / app Stop Juego. Enlaces a jugarbien.es y FEJAR.

## Flujo de trabajo
- Trabaja por fases. Usa plan mode (Shift+Tab) ANTES de implementar cada fase.
- git commit al final de cada fase con mensaje descriptivo.
- pytest en cada módulo antes de dar una fase por cerrada.
