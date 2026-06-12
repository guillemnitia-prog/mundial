"use client";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";

export default function CasinoPage() {
  const router = useRouter();
  return (
    <div>
      <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-[#14513c] px-4 py-3"
        style={{ background: "linear-gradient(180deg,#0c2a20,#0A1712)", paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-semibold" style={{ color: "#FFB300" }}>Casino</h1>
        <span className="ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: "var(--warning)", color: "#412402" }}>BETA</span>
      </header>

      <div className="p-4">
        {/* Ruleta — jugable */}
        <motion.button whileTap={{ scale: 0.99 }} onClick={() => router.push("/casino/ruleta")}
          className="mb-3 w-full overflow-hidden rounded-card border p-5 text-left"
          style={{ borderColor: "#FFB300", background: "#0c2a20" }}>
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-full border-2" style={{ borderColor: "#FFB300", background: "#FF5252" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#0A1712" strokeWidth="2"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2" /><path d="M12 3v18M3 12h18" /></svg>
            </div>
            <div className="flex-1">
              <div className="text-base font-semibold">Ruleta</div>
              <div className="text-xs text-muted">Rojo, negro o pleno. Saldo virtual.</div>
            </div>
            <span className="rounded-full px-3 py-1.5 text-sm font-semibold" style={{ background: "var(--accent)", color: "#0A1712" }}>Jugar →</span>
          </div>
        </motion.button>

        {/* Slots — próximamente */}
        <div className="mb-5 w-full rounded-card border border-border bg-surface p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-full" style={{ background: "#FFB30022", color: "#FFB300" }}>
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M8 9v6M12 9v6M16 9v6" /></svg>
            </div>
            <div className="flex-1">
              <div className="text-base font-semibold">Slots</div>
              <div className="text-xs text-muted">Tira y a ver qué sale.</div>
            </div>
            <span className="rounded-full px-3 py-1 text-[11px] font-medium" style={{ background: "var(--accent-faint)", color: "var(--accent)" }}>Próximamente</span>
          </div>
        </div>

        <div className="rounded-card border border-[#14513c] p-5 text-center" style={{ background: "#0c2a20" }}>
          <div className="text-lg font-semibold" style={{ color: "#FFB300" }}>Más juegos, próximamente chavales</div>
          <p className="mx-auto mt-1 max-w-[260px] text-sm text-muted">Seguimos montando el casino. ¡La ruleta ya está lista!</p>
        </div>

        <p className="mt-6 px-1 text-[11px] leading-relaxed text-[#737373]">
          Saldo virtual y entretenimiento entre amigos. +18 · juego responsable · límites DGOJ.
          Ayuda: jugarbien.es · FEJAR. Ninguna apuesta es segura.
        </p>
      </div>
    </div>
  );
}
