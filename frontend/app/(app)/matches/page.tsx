"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, MatchListItem } from "@/lib/api";
import { matchDate } from "@/lib/format";
import { Skeleton, StateChip } from "@/components/ui";

export default function MatchesPage() {
  const [matches, setMatches] = useState<MatchListItem[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const data = await api.get<MatchListItem[]>("/matches");
    setMatches(data);
  }, []);

  useEffect(() => { load(); }, [load]);

  async function onRefresh() {
    setRefreshing(true);
    try { await load(); } finally { setRefreshing(false); }
  }

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-2 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Partidos</h1>
        <button onClick={onRefresh} className="ml-auto text-sm text-accent">{refreshing ? "…" : "Actualizar"}</button>
      </header>

      <div className="flex flex-col gap-2 p-4">
        {!matches && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-20" />)}
        {matches?.length === 0 && <p className="text-center text-muted">No hay partidos.</p>}
        {matches?.map((m) => (
          <Link key={m.id} href={`/matches/${m.id}`} className="rounded-card border border-border bg-surface p-4">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted">
                {m.stage === "group" ? `Grupo ${m.group_label ?? ""}` : m.stage} · {matchDate(m.utc_date)}
              </span>
              <StateChip state={m.state} />
            </div>
            <div className="mt-2 flex items-center justify-between">
              <span className="text-[15px] font-medium">{m.home ?? "Por definir"} <span className="text-muted">vs</span> {m.away ?? "Por definir"}</span>
            </div>
            <div className="mt-1 text-xs">
              {m.state === "pendiente" ? (
                <span className="text-[#737373]">Análisis pendiente — se generará el día del partido</span>
              ) : m.n_picks > 0 ? (
                <span className="text-accent">{m.n_picks} apuesta{m.n_picks > 1 ? "s" : ""} de valor</span>
              ) : (
                <span className="text-muted">Sin apuesta de valor</span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
