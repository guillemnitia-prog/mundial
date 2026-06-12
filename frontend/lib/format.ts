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

// Explicación concisa de POR QUÉ se recomienda (a partir de prob modelo vs justa, EV y confianza).
export function whyRecommendation(
  market: string, outcome: string, modelProb: number, fairProb: number,
  evPct: number, confidence: string | null, home?: string, away?: string,
): string {
  const label = outcomeLabel(market, outcome, home, away);
  const m = Math.round(modelProb * 100);
  const f = Math.round(fairProb * 100);
  const per10 = ((evPct / 100) * 10).toFixed(2).replace(".", ",");
  return (
    `Nuestro modelo cree que «${label}» pasará con un ${m}% de probabilidad, ` +
    `bastante más que el ${f}% que reflejan las cuotas de las casas. ` +
    `Como lo vemos más probable de lo que paga la casa, la apuesta sale a cuenta: ` +
    `repitiéndola muchas veces, ganarías de media unos ${per10} € por cada 10 € apostados. ` +
    `Ojo: a corto plazo puede salir mal — ninguna apuesta es segura.`
  );
}

export const STATUS_LABEL: Record<string, string> = {
  scheduled: "Programado", live: "EN VIVO", finished: "Finalizado",
  postponed: "Aplazado", cancelled: "Cancelado",
};
