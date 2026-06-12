"use client";
import { motion } from "framer-motion";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} />;
}

export function StateChip({ state }: { state: string }) {
  const map: Record<string, { bg: string; fg: string }> = {
    analizado: { bg: "#00E676", fg: "#0A0A0A" },
    "en vivo": { bg: "#FF5252", fg: "#0A0A0A" },
    finalizado: { bg: "#262626", fg: "#A3A3A3" },
    pendiente: { bg: "#1f1f1f", fg: "#A3A3A3" },
  };
  const c = map[state] ?? map.pendiente;
  return (
    <span className="rounded-full px-2.5 py-0.5 text-[11px] font-medium" style={{ background: c.bg, color: c.fg }}>
      {state[0].toUpperCase() + state.slice(1)}
    </span>
  );
}

export function ConfidenceBadge({ confidence }: { confidence: string | null }) {
  if (!confidence) return null;
  const alta = confidence === "alta";
  return (
    <span
      className="rounded-full px-2 py-0.5 text-[10px] font-medium"
      style={{ background: alta ? "#00E676" : "#FFB300", color: alta ? "#0A0A0A" : "#412402" }}
    >
      {alta ? "Confianza alta" : "Confianza media"}
    </span>
  );
}

export function FormDots({ form }: { form: string[] }) {
  const color: Record<string, string> = { W: "#00E676", D: "#FFB300", L: "#FF5252" };
  return (
    <span className="flex gap-1">
      {form.length === 0 && <span className="text-[11px] text-muted">sin datos</span>}
      {form.map((r, i) => (
        <span key={i} className="text-[11px] font-medium" style={{ color: color[r] }}>
          {r}
        </span>
      ))}
    </span>
  );
}

export function Disclaimer() {
  return (
    <p className="px-4 py-4 text-[11px] leading-relaxed text-[#737373]">
      Cuotas region=eu como proxy de Bet365.es/Sportium; pueden diferir. Ninguna apuesta es segura.
      +18 · juego responsable · límites DGOJ. Ayuda:{" "}
      <a href="https://www.jugarbien.es" className="underline">jugarbien.es</a> · FEJAR.
    </p>
  );
}

export function Press({ children, onClick, className = "", style }: any) {
  return (
    <motion.button whileTap={{ scale: 0.97 }} transition={{ duration: 0.15 }} onClick={onClick} className={className} style={style}>
      {children}
    </motion.button>
  );
}
