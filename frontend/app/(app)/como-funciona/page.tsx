"use client";
import { useRouter } from "next/navigation";

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4">
      <div className="mb-1 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full text-[12px] font-semibold" style={{ background: "var(--accent)", color: "#0A0A0A" }}>{n}</span>
        <span className="text-[15px] font-medium">{title}</span>
      </div>
      <div className="text-[13px] leading-relaxed text-muted">{children}</div>
    </div>
  );
}

export default function HowItWorksPage() {
  const router = useRouter();
  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Cómo funciona</span>
      </header>

      <div className="flex flex-col gap-3 p-4">
        <p className="text-sm text-muted">
          Las probabilidades <span className="text-fg">no son una opinión</span>: salen de un modelo
          estadístico que vive dentro de la app. Funciona así:
        </p>

        <Step n="1" title="Goles esperados (Dixon-Coles)">
          Aprende la <span className="text-accent">fuerza de ataque y defensa</span> de cada selección a
          partir de <span className="text-fg">~49.000 partidos internacionales reales</span> (1872–hoy).
          Los partidos recientes pesan más. Con eso calcula la probabilidad de cada marcador y de ahí
          salen todos los mercados (ganador, más/menos goles, que marquen ambos…).
        </Step>

        <Step n="2" title="Fuerza de cada equipo (Elo)">
          Cada selección tiene una <span className="text-accent">puntuación Elo</span> (de eloratings.net).
          La diferencia de Elo da la probabilidad de ganar. La ventaja de jugar en casa solo cuenta para
          los <span className="text-fg">anfitriones</span> (USA, Canadá, México); el resto, campo neutral.
        </Step>

        <Step n="3" title="Se combinan los dos">
          La probabilidad final es una <span className="text-accent">mezcla calibrada</span> de ambos
          modelos. El peso se eligió comparándolo contra miles de resultados pasados: la mezcla acierta
          más que cada modelo por separado.
        </Step>

        <Step n="4" title="Y solo recomienda si hay valor">
          Compara la probabilidad del modelo con la <span className="text-accent">probabilidad “justa”</span>
          que esconden las cuotas (sin el margen de la casa). Solo sugiere apostar si el modelo lo ve
          claramente más probable que la casa (<span className="text-fg">≥70%</span>), con valor positivo
          y cuota ≥ 1,40. Si nada lo cumple: “Sin apuesta de valor”.
        </Step>

        <div className="rounded-card p-4 text-[12px] leading-relaxed" style={{ background: "var(--accent-faint)" }}>
          <span className="font-medium text-accent">En resumen:</span> datos históricos + fuerza Elo →
          probabilidad propia → se compara con el mercado. Es estadística, no adivinación. Por eso
          <span className="text-fg"> ninguna apuesta es segura</span> y conviene jugar con responsabilidad.
        </div>

        <p className="px-1 pb-2 text-[11px] leading-relaxed text-[#737373]">
          +18 · juego responsable · límites DGOJ. Cuotas region=eu como proxy de Bet365.es/Sportium.
          Ayuda: jugarbien.es · FEJAR.
        </p>
      </div>
    </div>
  );
}
