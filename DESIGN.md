# DESIGN.md — Sistema visual y de plataforma

Contexto de diseño de la app. **Vinculante para todo el frontend.** Acordado el 2026-06-12.
Complementa `DECISIONS.md` (donde §1 queda actualizado al stack React).

---

## 0. Plataforma — móvil exclusivo (PWA)
- **Solo móvil.** PWA **instalable** en iPhone/Android. NO es una web responsive de escritorio:
  es **mobile-first real**, diseñada para pantalla de teléfono.
- Viewport objetivo: **375–430 px** de ancho (iPhone SE → Pro Max / Android grande).
- Patrones nativos obligatorios:
  - **Bottom tab bar** (navegación principal con el pulgar).
  - **Ergonomía de pulgar**: acciones primarias en la mitad inferior.
  - **Bottom-sheets** para detalles/acciones (no modales centrados de escritorio).
  - **Pull-to-refresh** en listas.
  - **Safe areas de iPhone** (`env(safe-area-inset-*)`, notch y home indicator).
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

## 4. Pantallas (navegación por bottom tabs, orientativo)
- **Partidos** (lista) → **Detalle de partido** (bottom-sheet o pantalla con análisis + 2 picks).
- **Mi saldo** (saldo individual + historial + aceptar/saltar apuestas).
- **Ranking** (grupo por saldo).
- **Quiniela de campeón** (picks de los 7).
- **Chat** (en directo).

## 5. Componentes con 21st.dev Magic
- Generar los componentes principales con el MCP de 21st.dev Magic y **re-tematizarlos** a los
  tokens de §2 (no usar sus colores por defecto).
- Candidatos: tarjeta de partido, bottom-sheet de detalle, chip de EV/cuota, botones
  apostar/saltar, barra de saldo, fila de ranking, burbujas de chat, bottom tab bar.

## 6. Regla de revisión (acordada)
> Al llegar al frontend, **construir y enseñar primero la pantalla de DETALLE DE PARTIDO a
> tamaño móvil** (con tokens aplicados) y esperar visto bueno **antes** de construir el resto.

## 7. Disclaimers (siempre visibles, integrados en el diseño)
- +18, riesgo real de pérdida; herramienta de análisis/entretenimiento, no inversión garantizada.
- Límites DGOJ y enlaces de juego responsable (jugarbien.es / FEJAR / autoexclusión).
- Aviso permanente de **cuota proxy `region=eu`** (no es Bet365.es/Sportium real).
