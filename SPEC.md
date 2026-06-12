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
5. Sugiere un stake según Kelly fraccionado (1/4) sobre un bankroll de grupo.

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
teams(id PK, name, fifa_code, elo REAL, confederation, is_host BOOL)
matches(id PK, utc_date, home_id FK, away_id FK, group_label, stage,
        neutral_venue BOOL, home_goals, away_goals, status)   -- stage: group|R32|R16|QF|SF|3RD|F
odds(id PK, match_id FK, bookmaker, market, outcome, price REAL, captured_at)
predictions(id PK, match_id FK, market, outcome, model_prob REAL, fair_prob REAL,
            offered_odds REAL, ev REAL, recommended_stake REAL, rank INT, created_at)
users(id PK, username UNIQUE, password_hash, role, has_onboarded BOOL, created_at)
champion_picks(user_id PK FK, team_id FK, created_at)   -- inmutable
chat_messages(id PK, user_id FK, content, created_at)
bankroll(id PK, as_of_date, balance REAL)
bets(id PK, match_id FK, market, outcome, stake REAL, odds REAL,
     result, pnl REAL, clv REAL, placed_at)
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

## 5. Bankroll (Kelly fraccionado)

- f* = (b·p − q) / b ; b = cuota−1, p = model_prob, q = 1−p. Solo si f*>0.
- Usar **1/4 Kelly**. Cap absoluto: nunca >5% del bankroll en una apuesta.
- Bankroll de grupo = 7 × 50 € = 350 €. Recalcular % sobre el balance ACTUAL.
- No perseguir pérdidas. Si el bankroll cae >50%, reducir la unidad a la mitad.

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
- GET  /bankroll  /  POST /bets  (registrar apuesta y resultado)
- WS   /ws/chat

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
11. api/main.py + frontend mínimo.
12. scheduler/daily_refresh.py.

pytest en cada fase. Commit al cerrar cada fase.
