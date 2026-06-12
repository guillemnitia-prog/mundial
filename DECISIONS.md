# DECISIONS.md — WorldCup Betting Analyzer

Decisiones técnicas acordadas en la **Fase 0 (entrevista)**. No modifica `SPEC.md` ni
`CLAUDE.md`: los complementa. Donde haya conflicto aparente, las **reglas no negociables de
CLAUDE.md** mandan. Fecha: 2026-06-12.

---

## 1. Frontend
> **Actualizado (brief visual del usuario):** se cambia a **Next.js PWA (React)**. El brief de
> `DESIGN.md` (PWA instalable, Framer Motion, bottom-sheets, componentes de 21st.dev Magic) es
> React puro e incompatible con Jinja2+HTMX. Ver `DESIGN.md` para tokens y plataforma.
- **Next.js (App Router) + React + TypeScript + Tailwind + Framer Motion**, PWA instalable
  (mobile-only, 375–430 px). Componentes principales vía MCP 21st.dev Magic, re-tematizados.
- **FastAPI = API JSON pura** (no renderiza HTML). Auth JWT en cookie httpOnly; CORS con
  credenciales para el front. Chat por WebSocket sigue en FastAPI.
- (Histórico) Jinja2+HTMX fue la elección inicial de Fase 0; descartada al recibir el brief visual.

## 2. Modelo — calibración del ensemble
- Pesos Dixon-Coles vs Elo por **grid-search minimizando RPS/Brier** sobre los resultados
  internacionales históricos (Kaggle, ~49k partidos), con **validación walk-forward temporal**
  (entrenar pasado → evaluar futuro, sin fuga de datos).
- Arrancar 50/50; **fijar el peso** tras calibrar. Si el walk-forward sale inestable, fallback
  a 50/50 fijo.
- Calibrar contra **cuotas de cierre** queda como mejora futura (no tenemos histórico de odds
  fiable ahora). La validación previa al torneo (SPEC 3.4) usa los resultados disponibles.
- Detalles que zanjo como default (revisables en su fase): time-decay ξ calibrado por RPS;
  matriz de marcadores truncada a 0–10 goles por equipo; restricción media(atk)=1.

## 3. Análisis detallado por partido (`GET /matches/{id}`)
Vista **completa y estructurada**:
- Elo y prob 1X2 de cada selección; forma reciente.
- Contexto: sede, neutral vs anfitrión (ventaja local solo USA/Canadá/México), fase.
- Tabla **model_prob vs fair_prob** por mercado + **overround** del bookie.
- Los **2 picks** con cuota, EV y stake.
- Heatmap de marcadores **opcional** (no bloqueante).

## 4. Presentación de EV y stake (UI)
> **Actualización (aclaración del usuario):** NO hay bote común. Cada usuario tiene un **saldo
> virtual individual** de 50 € de partida (`users.balance`). El stake se calcula y se muestra
> **por usuario sobre su saldo actual**. Ver §9.
- **EV en %** del importe (p.ej. +6,2 %).
- **Stake** en € sobre el **saldo individual del usuario** **y** su % del saldo (1/4 Kelly,
  tope 5 %), p.ej. *"Apuesta 8,50 € — 17% de tu saldo, cuota 1,75"*.
- Si el stake sale < 1 € (o < mínimo de la casa): **"demasiado pequeña, no apostar"**.
- Badge visible de **cuota proxy `region=eu`** y **disclaimer de juego responsable** siempre.

## 5. Edge cases

### 5.1 Eliminatorias (prórroga / penaltis)
- Modelamos y apostamos el **resultado a 90 minutos, 3 vías (empate incluido)**, casando
  exactamente el mercado h2h de The Odds API. Prórroga y penaltis **no afectan** a este mercado.
- "Pasar de ronda" (2 vías / To Qualify) queda como mercado distinto y mejora futura; nunca
  mezclar con h2h.

### 5.2 Alcance de los 2 picks
- Buscar EV en **todos los mercados derivados** de la matriz de marcadores: 1X2, Over/Under
  (2.5 y alternativos), BTTS, hándicap asiático, marcador exacto.
- Pipeline: derivar mercados → **filtrar cuota ≥ 1.40** → filtrar **EV > 0** → ordenar por EV →
  coger los **2 de mayor EV** sean del mercado que sean.

### 5.3 Casos límite de selección y estructura del torneo (honestidad estricta)
- Si tras el filtro quedan **<2** candidatos válidos, mostrar **0 o 1** (nunca inventar ni
  rellenar con EV≤0 o cuota<1.40).
- Solo analizar partidos con **rivales ya confirmados** por football-data. **No** predecir
  cruces de mejores terceros / bracket hasta que estén fijados (proyección de bracket = vista
  aparte futura, no entra en el flujo de picks).

## 6. Cuotas y línea de referencia (devig)
- Devig sobre el **consenso de bookies `region=eu`** de The Odds API como prob justa.
- **Aviso permanente** de que es proxy de Bet365.es / Sportium (sin API; prohibido scrapear).
- Si existe `ODDSPAPI_KEY`, usar **Pinnacle como ancla sharp preferente** (opcional, no requisito).
- The Odds API no trae Pinnacle: por eso el consenso eu es la base.

## 7. Operativa de datos

### 7.1 Presupuesto The Odds API (500 cr/mes ≈ 16/día)
- **1 refresco diario** en el scheduler, solo de partidos en las **próximas 48 h**, mercados
  limitados (`h2h,totals,spreads`).
- **Contador de créditos persistido en SQLite** que **corta** antes de exceder el límite mensual.
- Refresco extra cerca del kickoff descartado por presupuesto (revisable si sobran créditos).

### 7.2 Resultados, liquidación y CLV
- **Resultados automáticos**: football-data rellena `home_goals/away_goals/status` en el
  refresco diario.
- **Aceptar/saltar**: cada usuario acepta una recomendación (botón "apostar" → `POST /bets`,
  crea `bets` con su stake individual) o la salta (no crea fila). El saldo refleja solo lo apostado.
- **Liquidación automática** al cerrarse el partido (`status=finished`): gana →
  `balance += stake·(odds−1)`; pierde → `balance −= stake`; movimiento en `balance_ledger`.
  Ranking de grupo por saldo (`GET /ranking`).
- **CLV** = cuota apostada vs **cuota de cierre cacheada**.

## 8. Defaults menores zanjados (sin pregunta, revisables)
- **Auth**: JWT en **cookie httpOnly** (HTMX la envía sola; protege también el WebSocket).
  Algoritmo y expiración según `.env` (HS256, 7 días).
- Credenciales de las 7 cuentas: leídas de fichero local **no versionado** o env por
  `seed_users.py`; hash **argon2**. Sin registro público; admin puede resetear.
- Champion pick **inmutable** una vez enviado; visible para todo el grupo.
- Chat: cargar **últimas 50** al conectar; mostrar username + hora; solo autenticados.

---

## Reglas no negociables (recordatorio, de CLAUDE.md — siempre por encima de lo anterior)
- Value betting con **EV > 0**; nunca recomendar sin value.
- Filtro de **cuota decimal ≥ 1.40** antes de ordenar por EV.
- **1/4 Kelly** sobre el **saldo individual** del usuario, tope **5 %** del saldo; recalcular
  sobre el saldo actual; reducir unidad a la mitad si el saldo cae >50 % del inicial.
- **Caché en SQLite**; nunca llamar APIs en cada request. Respetar límites (football-data
  10 req/min; The Odds API 500 cr/mes).
- Elo de **eloratings.net** (selecciones), nunca ClubElo. Ventaja local solo anfitriones.
- **No scrapear Bet365**. No commitear `.env`/keys/contraseñas.
- **Disclaimers de juego responsable visibles** (18+, límites DGOJ, autoexclusión, jugarbien.es / FEJAR).
