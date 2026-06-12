export const eur = (n: number) =>
  new Intl.NumberFormat("es-ES", { style: "currency", currency: "EUR" }).format(n);

export const pct = (n: number) => `${n.toFixed(1)}%`;

export const odds = (n: number) => n.toFixed(2);

export function matchDate(iso: string | null): string {
  if (!iso) return "Por confirmar";
  const d = new Date(iso);
  return d.toLocaleString("es-ES", {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

export function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "hace un momento";
  if (mins < 60) return `hace ${mins} min`;
  const h = Math.round(mins / 60);
  return `hace ${h} h`;
}

export const OUTCOME_LABELS: Record<string, string> = {
  home: "Gana local",
  away: "Gana visitante",
  draw: "Empate",
};

export function outcomeLabel(market: string, outcome: string, home?: string, away?: string): string {
  if (market === "1x2") {
    if (outcome === "home") return `${home ?? "Local"} gana`;
    if (outcome === "away") return `${away ?? "Visitante"} gana`;
    return "Empate";
  }
  if (market === "over_under") {
    const [side, line] = outcome.split("_");
    return `${side === "over" ? "Más" : "Menos"} de ${line} goles`;
  }
  if (market === "btts") return outcome === "yes" ? "Ambos marcan" : "No marcan ambos";
  return `${market} · ${outcome}`;
}

export const CONF_LABEL: Record<string, string> = { alta: "Confianza alta", media: "Confianza media" };
