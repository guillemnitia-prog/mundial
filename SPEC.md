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
        neutral_venue BOOL, home_goals, away_goals, status,
        analysis_status, analysis_stage, analyzed_at)   -- stage: group|R32|R16|QF|SF|3RD|F
        -- external_id: id de football-data (upsert idempotente). home/away NULL en eliminatorias
        -- aún sin definir (no se analizan hasta confirmarse).
        -- analysis_status: pending|analyzed (el análisis se genera el DÍA del partido).
        -- analysis_stage: preliminary|final (pasada de la mañana vs pre-partido). analyzed_at: timestamp.
odds(id PK, match_id FK, bookmaker, market, outcome, price REAL, captured_at)
predictions(id PK, match_id FK, market, outcome, model_prob REAL, fair_prob REAL,
            offered_odds REAL, ev REAL, recommended_stake REAL, rank INT, confidence, created_at)
            -- confidence: alta|media (solo se guardan recomendaciones que cumplen los filtros de §4)
users(id PK, username UNIQUE, password_hash, role, has_onboarded BOOL,
      balance REAL DEFAULT 50.0, created_at)   -- saldo virtual individual, 50 € de partida
champion_picks(user_id PK FK, team_id FK, created_at)   -- inmutable
chat_messages(id PK, user_id FK, content, created_at)
-- NO hay bote común: cada usuario tiene su propio saldo (users.balance) y su propio historial.
bets(id PK, user_id FK, match_id FK, prediction_id FK, market, outcome,
     stake REAL, odds REAL, decision, recommended_stake REAL, status, result, pnl REAL, clv REAL,
     placed_at, settled_at)   -- status: open|won|lost|void. UNIQUE(user_id,prediction_id).
     -- stake = importe EFECTIVO. decision: recommended|modified|rejected|default (§5.3).
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

## 4. Value betting — conservador y selectivo

Filosofía: **mejor pocas apuestas sólidas que muchas dudosas.** El sistema es deliberadamente
selectivo; no rellena recomendaciones para cumplir un cupo.

1. Implícita = 1 / cuota_decimal.
2. Quitar margen: normalización proporcional (dividir cada implícita por la suma de
   implícitas del mercado). El exceso de la suma sobre 1 es el overround.
3. Value si model_prob > fair_prob del bookie.
4. EV = model_prob·(cuota−1) − (1−model_prob). Apostar solo si EV>0.
5. **Doble filtro obligatorio (ambas condiciones a la vez):**
   - (a) **model_prob ≥ MIN_CONFIDENCE** (por defecto **0.70**, configurable). Alta confianza.
   - (b) **EV > 0** tras quitar el margen.
6. **Filtro de cuota mínima 1.40**: descartar cualquier candidato con cuota < 1.40 ANTES de
   ordenar. Configurable (MIN_ODDS=1.40). Stake = ¼ Kelly con tope 5% (§5).
7. **Clasificar por confianza** cada recomendación: **Alta / Media** según `model_prob` y el
   margen de EV. Guardar en `predictions.confidence` y mostrarlo en la UI.
8. **No forzar 2.** Seleccionar hasta 2 candidatos que pasen 5–6, ordenados por confianza/EV.
   Si **ninguno** cumple, mostrar **"Sin apuesta de valor en este partido"** (0 recomendaciones).
   Nunca inventar una mala apuesta.
9. **Transparencia en la UI**: mostrar la **probabilidad real estimada por el modelo**, la **cuota**,
   el **EV%** y un **recordatorio de que ninguna apuesta es segura**.
10. Registrar CLV (cuota apostada vs cierre) como métrica de habilidad real.

---

## 5. Saldo individual y dimensionamiento del stake (Kelly fraccionado)

**Saldo virtual individual (NO bote común).** Cada usuario empieza con 50 € virtuales
(`users.balance DEFAULT 50.0`). Son saldos independientes. Cada usuario acepta ("apostar") o se
salta ("saltar") cada recomendación; su saldo refleja SOLO lo que apostó.

**Saldo editable (self-service).** Cada usuario puede **ingresar**, **retirar** o **fijar** su
propio saldo cuando quiera (`POST /me/balance/{deposit|withdraw|set}`); cada movimiento se registra
en `balance_ledger` (con `bet_id = NULL`). Retirar nunca por debajo de 0. El saldo de partida sigue
siendo 50 €.

### 5.1 Cálculo del stake (`bankroll/kelly.py`), por usuario
Política de dimensionamiento (decidida por el grupo): cada apuesta es **significativa**.
- **stake = max(20% del saldo, 10 €)**, limitado al **25% del saldo** (`MIN_STAKE_PCT=0.20`,
  `MAX_STAKE_EUR` mínimo `MIN_STAKE_EUR=10`, `MAX_STAKE_PCT=0.25`).
- **Nunca recomendar menos de 10 €.** Si el saldo del usuario es **< 10 €**, no se recomienda
  apostar (importe demasiado pequeño).
- En saldos bajos donde 10 € supera el 25%, manda el mínimo de 10 € (acotado al saldo).
- Solo recomendar si **EV>0, confianza ≥ MIN_CONFIDENCE y cuota ≥ 1.40** (filtro en `value/ev.py`).
- Devolver stake en **€ y en % del saldo**. El € se **recalcula individualmente** por usuario.
- `predictions.recommended_stake` guarda la **fracción nominal** (0.20), user-independent; el € por
  usuario lo calcula `kelly.user_stake(saldo)`.
- (Nota: sustituye la política conservadora previa de ¼ Kelly + tope 5%; sin halving.)

### 5.2 Liquidación automática
- Al terminar el partido (`matches.status = finished` con goles), liquidar cada `bets` abierta:
  - **gana** → `balance += stake·(odds−1)`, `pnl = +stake·(odds−1)`, `status=won`.
  - **pierde** → `balance −= stake`, `pnl = −stake`, `status=lost`.
  - **anulada** → `status=void`, `pnl=0`, devolver stake si procede.
- Registrar cada movimiento en `balance_ledger` (delta + balance_after).
- La liquidación usa SIEMPRE el **importe efectivo** de cada usuario (§5.3), no el recomendado.
- Cada usuario ve su saldo, su historial de apuestas y un **ranking del grupo por saldo**.

### 5.3 Decisión de apuesta por usuario
Sobre cada recomendación, cada usuario tiene cuatro caminos (`bets.decision`):
- **Aceptar** (`recommended`): apuesta con el importe recomendado.
- **Rechazar** (`rejected`): no apuesta; no afecta al saldo (`status=void`, queda fuera).
- **Cambiar importe** (`modified`): acepta con su propio importe. Validar
  **MIN_STAKE_EUR (10 €) ≤ importe ≤ saldo actual**; si no, no permitir confirmar.
- **Deshacer**: borra la decisión (la apuesta vuelve a estar disponible: reaparecen Aceptar/
  Rechazar/Cambiar y el dinero comprometido se libera). Permitido dentro de la ventana (ver lock).
- **No hacer nada** (`default`): cuenta como apuesta con el importe recomendado (el comportamiento
  por defecto es apostar lo recomendado salvo rechazo explícito).

Reglas:
- **Importe efectivo** = recomendado (aceptar / no hacer nada) o personalizado (cambiar importe).
  Se guarda en `bets.stake` de cada usuario; `bets.recommended_stake` guarda el € recomendado.
- Como cada usuario puede tener un importe distinto en la misma apuesta, el PnL se calcula
  **individualmente** en la liquidación (§5.2) con el importe efectivo.
- Estados: `recommended | modified | rejected | default` → tras el partido pasan a `won/lost`
  (las `rejected` quedan fuera).
- **Lock a T‒30**: todas las acciones (aceptar/rechazar/cambiar/**deshacer**) están permitidas
  **hasta 30 min antes** del partido (`LOCK_MINUTES_BEFORE=30`); a partir de ahí queda **bloqueado**
  (lo que haya entonces cuenta, incluido `default`). El scheduler materializa los `default` al
  bloquear el partido (Fase 12). `betting_open(match, now)` centraliza esta regla.
- UI (detalle de partido, móvil): botones **Aceptar / Rechazar / Cambiar importe**; con decisión ya
  tomada aparecen **Cambiar** y **Deshacer**. "Cambiar importe" abre un **bottom-sheet** con importe,
  beneficio potencial en vivo y % del saldo, y botón Confirmar. Tras T‒30: "Cerrado (faltan <30 min)".

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
- POST /predictions/{id}/decision  (decisión del usuario: accept|reject|modify [+amount]; §5.3)
- GET  /me/bets  (historial de apuestas del usuario)
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
8. ingest/odds_api.py + value/devig.py + value/ev.py (doble filtro confianza+EV, cuota 1.40; §4).
9. bankroll/kelly.py.
10. chat/ (WebSocket).
11. api/main.py + frontend (PWA Next.js, mobile-only; ver DESIGN.md). Empezar por la pantalla
    de detalle de partido.
12. scheduler/daily_refresh.py (pasada de la mañana: análisis de los partidos del día +
    liquidación + push) y scheduler/pre_match_refresh.py (pasada final ~2h y ~1h antes:
    alineaciones/lesiones + cuotas frescas + recálculo). Ver §11. Opcional: ingest/api_football.py.
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

---

## 11. Análisis solo el día del partido (ciclo de vida)

El análisis de cada partido se genera **automáticamente el día en que se juega, no antes**.
Lo orquesta el scheduler leyendo `matches.utc_date`.

### 11.1 Ciclo de vida (estado visible en la UI)
`pendiente → analizado → en vivo → finalizado`. Se deriva de (`matches.status`, `analysis_status`):
- **pendiente**: aún no es el día del partido. `analysis_status=pending`. En la lista aparece con
  la etiqueta **"Análisis pendiente — se generará el día del partido"** (sin picks).
- **analizado**: es el día del partido y ya hay análisis. `analysis_status=analyzed`.
- **en vivo**: `status=live`.
- **finalizado**: `status=finished` (con liquidación automática, §5.2).

### 11.2 Dos pasadas el día del partido
Para cada partido que se juega **hoy**:
1. **Pasada de la mañana** (`scheduler/daily_refresh.py`): análisis completo con los datos más
   frescos disponibles (forma reciente, Elo actualizado, fuerzas del modelo, probabilidades,
   cuotas, EV, stake). `analysis_status=analyzed`, `analysis_stage=preliminary`, `analyzed_at=now`.
2. **Pasada final** (`scheduler/pre_match_refresh.py`, ~2h y ~1h antes del pitido): alineaciones
   confirmadas y bajas/lesiones de última hora (API-Football, cacheado por el límite 100/día) +
   cuotas más recientes; **recalcula todo**. `analysis_stage=final`. Si la recomendación cambia,
   actualiza la apuesta mostrada y la **notificación de "1h antes"** (§10).

Cada análisis se guarda con timestamp (`analyzed_at`). La UI muestra **"Actualizado hace X min"**
y si el análisis es **preliminar** o **final**.

### 11.3 Selección conservadora
El análisis aplica el doble filtro de §4 (confianza ≥ MIN_CONFIDENCE **y** EV>0, cuota ≥ 1.40).
Si ningún mercado lo cumple, el partido queda **analizado pero "Sin apuesta de valor"** (0 picks).
