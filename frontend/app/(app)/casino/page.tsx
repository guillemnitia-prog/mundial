"use client";
import { motion } from "framer-motion";

function GameCard({ title, desc, icon, color }: { title: string; desc: string; icon: React.ReactNode; color: string }) {
  return (
    <div className="relative overflow-hidden rounded-card border border-border bg-surface p-5">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full" style={{ background: `${color}22`, color }}>
        {icon}
      </div>
      <div className="text-base font-medium">{title}</div>
      <div className="mt-0.5 text-xs text-muted">{desc}</div>
      <span className="mt-3 inline-block rounded-full px-3 py-1 text-[11px] font-medium" style={{ background: "var(--accent-faint)", color: "var(--accent)" }}>
        Próximamente
      </span>
    </div>
  );
}

export default function CasinoPage() {
  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-2 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Casino</h1>
        <span className="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: "var(--warning)", color: "#412402" }}>BETA</span>
      </header>

      <div className="p-4">
        <motion.div
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
          className="mb-5 rounded-card border p-6 text-center" style={{ borderColor: "var(--accent)", background: "var(--accent-faint)" }}
        >
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full" style={{ background: "var(--accent)", color: "#0A0A0A" }}>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3" /><path d="M12 3v3M12 18v3M3 12h3M18 12h3" />
            </svg>
          </div>
          <div className="text-xl font-semibold text-accent">Próximamente chavales</div>
          <p className="mx-auto mt-2 max-w-[260px] text-sm text-muted">
            Estamos montando el casino: ruleta, slots y más. Mientras tanto, ¡a por los partidos!
          </p>
        </motion.div>

        <div className="mb-2 text-sm font-medium text-muted">Lo que viene</div>
        <div className="grid grid-cols-2 gap-3">
          <GameCard
            title="Ruleta" desc="Rojo o negro, tú decides" color="#FF5252"
            icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2" /><path d="M12 3v18M3 12h18" /></svg>}
          />
          <GameCard
            title="Slots" desc="Tira y a ver qué sale" color="#FFB300"
            icon={<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M8 9v6M12 9v6M16 9v6" /></svg>}
          />
        </div>

        <p className="mt-6 px-1 text-[11px] leading-relaxed text-[#737373]">
          Saldo virtual y entretenimiento entre amigos. +18 · juego responsable · límites DGOJ.
          Ayuda: jugarbien.es · FEJAR. Ninguna apuesta es segura.
        </p>
      </div>
    </div>
  );
}
