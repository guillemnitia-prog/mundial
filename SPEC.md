# SPEC.md — WorldCup Betting Analyzer

Especificación técnica completa. CLAUDE.md contiene las reglas operativas resumidas;
este documento es la referencia detallada.

---

## 0. Objetivo y alcance

App privada para un grupo de 7 amigos. Para cada partido del Mundial 2026:
1. Muestra un análisis detallado (fuerza de cada selección, forma, Elo, contexto).
2. Calcula probabilidades con un modelo propio (ensemble Dixon-Coles + Elo).
3. Compara contra las cuotas del mercado (sin margen) y detecta value (EV>0).
4. Propone exactamente 2 pronósticos por partido, ambos con cuota decimal >= 1.40.
5. Sugiere un stake según Kelly fraccionado (1/4) sobre el **saldo virtual individual** de
   cada usuario (50 € de partida por usuario; NO es un bote común). El stake en € se recalcula
   por usuario sobre su saldo ACTUAL, aunque el pronóstico (outcome + cuota) sea el mismo para todos.

Aviso permanente en la UI: batir al mercado a largo plazo es muy difícil; esto es
una herramienta de análisis y entretenimiento, NO una inversión garantizada.

---

## 1. Fuentes de datos (gratis / baratas)

| Uso | Fuente | Plan | Límite | Notas |
|-----|--------|------|--------|-------|
| Fixtures / resultados / clasificación | football-data.org | Free | 10 req/min | Incluye el Mundial FIFA. Auth header X-Auth-Token. |
| Histórico internacional (entrenar) | Kaggle martj42 "International football results 1872–2026" | Gratis (CSV) | — | 49.393 partidos. Descargar 1 vez; versión daily-updates durante el torneo. |
| Fuerza de selección (Elo) | eloratings.net | Gratis | — | Scraping de TSV o dataset Kaggle ya scrapeado. Selecciones (NO ClubElo). |
| Cuotas | The Odds API | Free | 500 créditos/mes (~16/día) | sport=soccer_fifa_world_cup, region=eu, markets=h2h,totals,spreads. 1 crédito por mercado×región. |
| Línea sharp (Pinnacle) opcional | OddsPapi | Free | 250 req/mes | The Odds API NO trae Pinnacle. |
| Alineaciones / lesiones opcional | API-Football | Free | 100 req/día | Cachear agresivo. |

Regla: toda respuesta de API se cachea en SQLite. Nunca llamar en cada request.

---

## 2. Modelo de datos (SQLite)

```sql
teams(id PK, external_id UNIQUE, name, fifa_code, elo REAL, confederation, is_host BOOL)
matches(id PK, external_id UNIQUE, utc_date, home_id FK NULL, away_id FK NULL, group_label, stage,
        neutral_venue BOOL, home_goals, away_goals, status)   -- stage: group|R32|R16|QF|SF|3RD|F
        -- external_id: id de football-data (upsert idempotente). home/away NULL en eliminatorias
        -- aún sin definir (no se analizan hasta confirmarse).
odds(id PK, match_id FK, bookmaker, market, outcome, price REAL, captured_at)
predictions(id PK, match_id FK, market, outcome, model_prob REAL, fair_prob REAL,
            offered_odds REAL, ev REAL, recommended_stake REAL, rank INT, created_at)
users(id PK, username UNIQUE, password_hash, role, has_onboarded BOOL,
      balance REAL DEFAULT 50.0, created_at)   -- saldo virtual individual, 50 € de partida
champion_picks(user_id PK FK, team_id FK, created_at)   -- inmutable
chat_messages(id PK, user_id FK, content, created_at)
-- NO hay bote común: cada usuario tiene su propio saldo (users.balance) y su propio historial.
bets(id PK, user_id FK, match_id FK, prediction_id FK, market, outcome,
     stake REAL, odds REAL, status, result, pnl REAL, clv REAL,
     placed_at, settled_at)   -- status: open|won|lost|void. Una fila por usuario y apuesta.
balance_ledger(id PK, user_id FK, bet_id FK, delta REAL, balance_after REAL, created_at)
push_subscriptions(id PK, user_id FK, endpoint, p256dh, auth, created_at)  -- Web Push (una por dispositivo)
api_cache(id PK, source, cache_key UNIQUE, response_json, fetched_at, expires_at)  -- caché HTTP (TTL)
```

---

## 3. Modelo predictivo

### 3.1 Dixon-Coles (base)
- Goles ~ Poisson con fuerzas de ataque/defensa por equipo + ventaja local.
  - λ_local = exp(μ + atk_local + def_visit + γ·local)   (γ solo si anfitrión)
  - λ_visit = exp(μ + atk_visit + def_local)
- Corrección de bajos marcadores con τ(x,y) y parámetro ρ:
  - τ(0,0)=1−λμρ ; τ(0,1)=1+λρ ; τ(1,0)=1+μρ ; τ(1,1)=1−ρ ; resto = 1
- P(X=x,Y=y) = τ(x,y)·Pois(x;λ)·Pois(y;μ)
- Ajuste por máxima verosimilitud (scipy.optimize.minimize), restricción media(atk)=1.
- **Time-decay:** peso w = exp(−ξ·Δt_dias). Optimizar log-verosimilitud ponderada.
  Calibrar ξ por validación (RPS/Brier) sobre temporadas pasadas.

### 3.2 Elo (selecciones)
- W_e = 1 / (1 + 10^(−dr/400)), dr = R_local − R_visit (+100 al anfitrión si aplica).
- Mapear Elo→prob de 3 vías calibrando una tasa de empate por bin de |dr|.

### 3.3 Ensemble
- Prob final = media ponderada de Dixon-Coles y Elo (empezar 50/50; recalibrar con
  RPS sobre cuotas de cierre históricas). De la matriz de marcadores derivar TODOS
  los mercados: 1X2, Over/Under (2.5 y alternativos), BTTS, marcador exacto, hándicap asiático.

### 3.4 Validación previa al torneo
- Antes de apostar un euro: backtest contra cuotas de cierre, medir RPS y Brier,
  comparar con el cierre del mercado. Si el modelo no se acerca al cierre, no hay ventaja.

---

## 4. Value betting

1. Implícita = 1 / cuota_decimal.
2. Quitar margen: normalización proporcional (dividir cada implícita por la suma de
   implícitas del mercado). El exceso de la suma sobre 1 es el overround.
3. Value si model_prob > fair_prob del bookie.
4. EV = model_prob·(cuota−1) − (1−model_prob). Apostar solo si EV>0.
5. **Filtro de cuota mínima 1.40**: descartar cualquier candidato con cuota < 1.40
   ANTES de ordenar por EV. Configurable (MIN_ODDS=1.40).
6. Seleccionar los 2 de mayor EV por partido. Si quedan <2 con EV>0, mostrar los que haya.
7. Registrar CLV (cuota apostada vs cierre) como métrica de habilidad real.

---

## 5. Saldo individual y dimensionamiento del stake (Kelly fraccionado)

**Saldo virtual individual (NO bote común).** Cada uno de los 7 usuarios empieza con 50 €
virtuales (`users.balance DEFAULT 50.0`). Son 7 saldos independientes. Cada usuario acepta
("apostar") o se salta ("saltar") cada recomendación; su saldo refleja SOLO lo que apostó.

### 5.1 Cálculo del stake (`bankroll/kelly.py`), por usuario
- Fracción Kelly: f = ((odds−1)·p − (1−p)) / (odds−1) ; p = model_prob. Solo si f>0.
- **1/4 Kelly sobre el saldo ACTUAL del usuario**: `stake = saldo · (f / 4)`.
- **Tope duro 5%**: nunca más del 5% del saldo en una apuesta. Si ¼ Kelly lo supera, recortar
  a `0.05 · saldo`.
- **Mínimo**: si el stake sale < 1 € (o por debajo del mínimo de la casa), marcar
  **"demasiado pequeña, no apostar"** (no se recomienda apostar).
- Solo recomendar si **EV>0 y cuota ≥ 1.40**. Nunca todo el saldo en un partido
  (p.ej. con 50 €, recomendar 8–15 €, jamás 50 €).
- Devolver stake en **€ y en % del saldo** (p.ej. "Apuesta 8,50 € — 17% de tu saldo, cuota 1,75").
- El € se **recalcula individualmente** sobre el saldo de cada usuario, aunque el pronóstico
  (outcome + cuota) sea el mismo para todos.
- No perseguir pérdidas. Si el saldo de un usuario cae >50% del inicial, reducir la unidad a la mitad.

### 5.2 Liquidación automática
- Al terminar el partido (`matches.status = finished` con goles), liquidar cada `bets` abierta:
  - **gana** → `balance += stake·(odds−1)`, `pnl = +stake·(odds−1)`, `status=won`.
  - **pierde** → `balance −= stake`, `pnl = −stake`, `status=lost`.
  - **anulada** → `status=void`, `pnl=0`, devolver stake si procede.
- Registrar cada movimiento en `balance_ledger` (delta + balance_after).
- Cada usuario ve su saldo, su historial de apuestas y un **ranking del grupo por saldo**.

---

## 6. Auth, onboarding y chat

### 6.1 Auth
- 7 cuentas creadas por seed_users.py (lee usuarios/contraseñas de un fichero local
  NO versionado o variables de entorno; hashea con argon2). Sin registro público.
- Login → JWT httpOnly (o cookie de sesión). Middleware protege todas las rutas de la app
  y el WebSocket de chat. Rol admin puede resetear credenciales.

### 6.2 Onboarding (campeón)
- Si users.has_onboarded == false tras login → pantalla bloqueante con selector de las
  48 selecciones: "¿Qué equipo crees que ganará el Mundial?". Obligatorio.
- Guardar en champion_picks (inmutable), poner has_onboarded=true, entrar a la app.
- Pestaña "Quiniela de campeón" con los picks de los 7.

### 6.3 Chat
- /ws/chat (WebSocket). ConnectionManager mantiene las conexiones activas y hace broadcast.
- Persistir cada mensaje en chat_messages. Al conectar, enviar las últimas 50.
- Solo autenticados. Mostrar username + hora.

---

## 7. Endpoints (FastAPI) — orientativo

- POST /auth/login → token
- GET  /onboarding / POST /onboarding/champion
- GET  /matches  (lista con estado y pronósticos)
- GET  /matches/{id}  (análisis detallado + 2 pronósticos + EV + stake sugerido)
- GET  /champion-picks
- GET  /me/balance  (saldo actual + historial de apuestas del usuario)
- GET  /ranking  (ranking del grupo por saldo)
- POST /bets  (aceptar una recomendación: crea bet con stake individual; "saltar" no crea fila)
- GET  /push/vapid-public-key  (clave pública VAPID para suscribir el navegador)
- POST /push/subscribe  (guarda endpoint+p256dh+auth en push_subscriptions; tras el onboarding)
- WS   /ws/chat

La liquidación de apuestas es automática al cerrarse el partido (ver §5.2), no manual.

---

## 8. Mundial 2026 (contexto para el data model)

- 48 selecciones, 12 grupos (A–L) de 4. Avanzan 2 por grupo + 8 mejores terceros = 32.
- 104 partidos (72 grupos + 32 eliminatorias) en 39 días. 11 jun – 19 jul 2026.
- Anfitriones: USA, Canadá, México (marcar is_host y neutral_venue en consecuencia).
- Inauguración 11 jun (Estadio Azteca). Final 19 jul (MetLife, Nueva Jersey).
- El campo neutral es la norma salvo cuando juega un anfitrión.
- Verificar grupos/calendario finales en la web oficial de FIFA al iniciar.

---

## 9. Fases de implementación

1. Scaffolding de carpetas + git + requirements.
2. db/schema.py (SQLite, todas las tablas).
3. auth/ (seed_users, login, JWT, middleware) + onboarding.
4. ingest/football_data.py con caché.
5. models/dixon_coles.py (con time-decay, scipy).
6. models/elo_model.py + ingest de Elo.
7. models/ensemble.py + validación/backtest.
8. ingest/odds_api.py + value/devig.py + value/ev.py (filtro 1.40).
9. bankroll/kelly.py.
10. chat/ (WebSocket).
11. api/main.py + frontend (PWA Next.js, mobile-only; ver DESIGN.md). Empezar por la pantalla
    de detalle de partido.
12. scheduler/daily_refresh.py (refresco de datos + liquidación + disparo de notificaciones).
13. notifications/push.py (Web Push) + tabla push_subscriptions + endpoints /push/* +
    service worker en el front. Integrado con el scheduler (ver §10).

pytest en cada fase. Commit al cerrar cada fase.

---

## 10. Notificaciones push (Web Push)

- **Tecnología:** Web Push API (service worker + Push API). Funciona en **iPhone desde iOS 16.4**
  con la PWA **instalada** en pantalla de inicio.
- **Permiso:** pedirlo **tras el onboarding**, no al abrir la app.
- **Persistencia:** tabla `push_subscriptions(id, user_id, endpoint, p256dh, auth, created_at)`.
- **Backend:** módulo `notifications/push.py` con la librería **`pywebpush`**. Claves
  `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` en `.env` (generar con pywebpush en el setup).
- **Frontend:** service worker en `/public/sw.js` con listener del evento `push`.

### 10.1 Disparadores (los ejecuta el scheduler)
- **Tras liquidar** un partido terminado: push personalizada a **cada usuario con apuesta abierta**
  en ese partido (ganada/perdida).
- **1 hora antes** de cada partido: aviso con la **apuesta recomendada** para ese partido.

### 10.2 Plantillas de contenido
- **Ganó:**
  ```
  🟢 ¡Apuesta ganada! [Local] vs [Visitante]
  Apostaste X€ a [outcome] @[cuota] → +Y€
  Saldo actual: Z€
  ```
- **Perdió:**
  ```
  🔴 Apuesta perdida — [Local] vs [Visitante]
  Apostaste X€ a [outcome] @[cuota] → -X€
  Saldo actual: Z€
  ```
- **1h antes:**
  ```
  ⚽ En 1 hora: [Local] vs [Visitante]
  Apuesta recomendada: [outcome] @[cuota] — stake sugerido: X€
  ```
