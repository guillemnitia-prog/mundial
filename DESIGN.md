# DESIGN.md — Sistema visual y de plataforma

Contexto de diseño de la app. **Vinculante para todo el frontend.** Acordado el 2026-06-12.
Complementa `DECISIONS.md` (donde §1 queda actualizado al stack React).

---

## 0. Plataforma — móvil exclusivo (PWA)
- **Solo móvil.** PWA **instalable** en iPhone/Android. NO es una web responsive de escritorio:
  es **mobile-first real**, diseñada para pantalla de teléfono.
- Viewport objetivo: **375–430 px** de ancho (iPhone SE → Pro Max / Android grande).
- Patrones nativos obligatorios:
  - **Bottom tab bar FIJA** con 4 pestañas: **Partidos · Mi saldo · Ranking · Chat**.
  - **Ergonomía de pulgar**: botones/acciones principales en la **mitad inferior**.
  - **Bottom-sheets** para detalles/acciones (no modales centrados de escritorio).
  - **Pull-to-refresh** en la lista de partidos.
  - **Safe areas de iPhone** (`env(safe-area-inset-*)`, notch y home indicator).
- **PWA instalable**: `manifest.webmanifest` + **service worker** (`/public/sw.js`) + **icono**
  de app + **theme color `#0A0A0A`** + `display: standalone`. Instalable en pantalla de inicio.
- No hay layout de escritorio. Si se abre en desktop, se muestra centrada con ancho de móvil.

## 1. Stack frontend (resuelto)
- **Next.js (App Router) + React + TypeScript + Tailwind CSS + Framer Motion**, servido como
  **PWA instalable** (manifest + service worker; `next-pwa` o equivalente).
- **FastAPI = API JSON pura.** No renderiza HTML. CORS con credenciales para el front.
- Auth: **JWT en cookie httpOnly** (same-origin en prod tras reverse proxy; en dev, CORS
  `credentials: include` + `SameSite`).
- Componentes UI principales vía **MCP de 21st.dev Magic**, **unificados con los tokens de §2**.

## 2. Paleta y tokens (exactos)
| Token | Valor | Uso |
|---|---|---|
| `--bg` | `#0A0A0A` | Fondo de la app |
| `--surface` | `#141414` | Cards / superficies |
| `--border` | `#262626` | Bordes |
| `--accent` | `#00E676` | Verde acento (CTA, activos) |
| `--accent-hover` | `#00C853` | Verde hover/pressed |
| `--accent-faint` | `#00E67620` | Verde tenue (badges, fondos de chip) |
| `--text` | `#F5F5F5` | Texto principal |
| `--text-secondary` | `#A3A3A3` | Texto secundario |
| `--positive` | `#00E676` | Ganancia / EV+ |
| `--negative` | `#FF5252` | Pérdida |
| `--warning` | `#FFB300` | Aviso |

Paleta base: **negro y verde**.

## 3. Sistema visual
- **Radios**: cards **16–20 px**, botones **12 px**.
- **Glassmorphism sutil** en la barra superior (blur + transparencia ligera).
- **Framer Motion** para microinteracciones: **150–250 ms**, easing suave.
- **Confeti verde** al ganar una apuesta (settlement `won`).
- **Skeletons** de carga (no spinners genéricos) en listas y detalle.
- **Tipografía**: **Inter o Geist**. **Números tabulares** (`font-variant-numeric: tabular-nums`)
  para saldos, cuotas, EV, stakes y stats — que no "bailen" al actualizarse.

## 4. Pantallas — 4 tabs en la bottom bar fija
1. **Partidos** (lista, pull-to-refresh) → **Detalle de partido** (análisis + hasta 2 picks).
   Pantalla pivote del diseño. Por cada recomendación, botones **Aceptar / Rechazar / Cambiar
   importe** (ergonomía de pulgar, mitad inferior). "Cambiar importe" abre un **bottom-sheet** con
   campo de importe, **beneficio potencial en vivo** y **% del saldo**, y botón **Confirmar**
   (valida MIN_STAKE_EUR ≤ importe ≤ saldo). Editable hasta el inicio; al empezar, decisión
   bloqueada. Si no hay value: "Sin apuesta de valor en este partido". Ver SPEC §5.3.
2. **Mi saldo** (saldo individual + historial + aceptar/saltar apuestas).
3. **Ranking** (grupo por saldo). La **Quiniela de campeón** (picks de los 7) vive como
   sub-pantalla aquí (o cabecera), no como tab propia.
4. **Chat** (en directo).

## 5. Componentes con 21st.dev Magic
- Generar los componentes principales con el MCP de 21st.dev Magic y **re-tematizarlos** a los
  tokens de §2 (no usar sus colores por defecto).
- Candidatos: tarjeta de partido, bottom-sheet de detalle, chip de EV/cuota, botones
  apostar/saltar, barra de saldo, fila de ranking, burbujas de chat, bottom tab bar.

## 6. Regla de revisión (acordada)
> Al llegar al frontend, **construir y enseñar primero la pantalla de DETALLE DE PARTIDO a
> tamaño móvil** (con tokens aplicados) y esperar visto bueno **antes** de construir el resto.

## 6.b Notificaciones push (UX)
- Tecnología: **Web Push API** (service worker + Push API). Funciona en **iPhone desde iOS 16.4**
  con la PWA **instalada** en pantalla de inicio (requisito de Apple).
- **Pedir permiso de notificaciones TRAS el onboarding**, nunca al abrir la app por primera vez.
- Disparadores (los ejecuta el scheduler — ver SPEC §10):
  - **Tras liquidar** un partido terminado: push personalizada a cada usuario con apuesta abierta.
  - **1 hora antes** de cada partido: aviso con la apuesta recomendada.
- Plantillas de contenido (exactas):
  - Ganó: `🟢 ¡Apuesta ganada! [Local] vs [Visitante]` / `Apostaste X€ a [outcome] @[cuota] → +Y€`
    / `Saldo actual: Z€`
  - Perdió: `🔴 Apuesta perdida — [Local] vs [Visitante]` / `Apostaste X€ a [outcome] @[cuota] → -X€`
    / `Saldo actual: Z€`
  - 1h antes: `⚽ En 1 hora: [Local] vs [Visitante]` / `Apuesta recomendada: [outcome] @[cuota] —
    stake sugerido: X€`

## 7. Disclaimers (siempre visibles, integrados en el diseño)
- +18, riesgo real de pérdida; herramienta de análisis/entretenimiento, no inversión garantizada.
- Límites DGOJ y enlaces de juego responsable (jugarbien.es / FEJAR / autoexclusión).
- Aviso permanente de **cuota proxy `region=eu`** (no es Bet365.es/Sportium real).
