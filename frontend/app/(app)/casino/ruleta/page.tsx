"use client";
import { useRouter } from "next/navigation";

export default function RuletaPage() {
  const router = useRouter();
  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Ruleta</span>
      </header>

      <div className="p-4">
        <div className="rounded-card border p-8 text-center" style={{ borderColor: "#FFB300", background: "#0c2a20" }}>
          <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full border-2" style={{ borderColor: "#FFB300", background: "#FF5252" }}>
            <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#0A1712" strokeWidth="2"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="2" /><path d="M12 3v18M3 12h18" /></svg>
          </div>
          <div className="text-xl font-semibold" style={{ color: "#FFB300" }}>Próximamente chavales</div>
          <p className="mx-auto mt-2 max-w-[260px] text-sm text-muted">
            Estamos montando la ruleta con su rueda giratoria, estilo casino de verdad. ¡Muy pronto!
          </p>
        </div>
      </div>
    </div>
  );
}
