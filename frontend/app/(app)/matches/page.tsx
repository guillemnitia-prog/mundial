"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, MatchListItem } from "@/lib/api";
import { matchDate } from "@/lib/format";
import { flag } from "@/lib/flags";
import { Skeleton, StateChip } from "@/components/ui";

export default function MatchesPage() {
  const router = useRouter();
  const [matches, setMatches] = useState<MatchListItem[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const data = await api.get<MatchListItem[]>("/matches");
    setMatches(data);
  }, []);

  useEffect(() => {
    load();
    // Refresco automático cada 30 s (marcadores en vivo).
    const t = setInterval(() => { load(); }, 30000);
    return () => clearInterval(t);
  }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    try { await load(); } finally { setRefreshing(false); }
  }

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-2 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Partidos</h1>
        <button onClick={() => router.push("/como-funciona")} aria-label="Cómo funciona" className="ml-auto text-muted">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
        </button>
        <button onClick={onRefresh} className="text-sm text-accent">{refreshing ? "…" : "Actualizar"}</button>
      </header>

      <div className="flex flex-col gap-2 p-4">
        {!matches && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        {matches?.length === 0 && <p className="text-center text-muted">No hay partidos.</p>}
        {matches?.map((m) => {
          const hasScore = (m.status === "live" || m.status === "finished") && m.home_goals != null && m.away_goals != null;
          const hasPicks = m.n_picks > 0;
          return (
            <Link key={m.id} href={`/matches/${m.id}`}
              className="rounded-card border bg-surface p-4 transition active:scale-[0.99]"
              style={{ borderColor: hasPicks ? "var(--accent)" : "var(--border)" }}>
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted">
                  {m.stage === "group" ? `Grupo ${m.group_label ?? ""}` : m.stage} · {matchDate(m.utc_date)}
                </span>
                {m.status === "live" ? (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: "#FF5252", color: "#0A1712" }}>
                    <span className="h-1.5 w-1.5 rounded-full bg-[#0A1712] animate-pulse" /> EN VIVO
                  </span>
                ) : <StateChip state={m.state} />}
              </div>
              <div className="mt-2 grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className="shrink-0 text-lg leading-none">{flag(m.home_code)}</span>
                  <span className="truncate text-[15px] font-medium">{m.home ?? "Por definir"}</span>
                </div>
                <div className="w-14 text-center">
                  {hasScore
                    ? <span className="tabular text-lg font-semibold">{m.home_goals}-{m.away_goals}</span>
                    : <span className="text-sm text-muted">vs</span>}
                </div>
                <div className="flex min-w-0 items-center justify-end gap-1.5">
                  <span className="truncate text-right text-[15px] font-medium">{m.away ?? "Por definir"}</span>
                  <span className="shrink-0 text-lg leading-none">{flag(m.away_code)}</span>
                </div>
              </div>
              <div className="mt-2 text-xs">
                {m.state === "pendiente" ? (
                  <span className="text-[#737373]">Análisis pendiente — se generará el día del partido</span>
                ) : hasPicks ? (
                  <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-medium" style={{ background: "var(--accent-faint)", color: "var(--accent)" }}>
                    ★ {m.n_picks} apuesta{m.n_picks > 1 ? "s" : ""} de valor
                  </span>
                ) : (
                  <span className="text-muted">Sin apuesta de valor</span>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
