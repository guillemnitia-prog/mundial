"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { eur, odds as fmtOdds, outcomeLabel } from "@/lib/format";
import { Skeleton } from "@/components/ui";

interface Summary { balance: number; n_bets: number; n_open: number; n_won: number; n_lost: number; total_pnl: number; }
interface Bet { id: number; match_id: number; market: string; outcome: string; stake: number; odds: number; decision: string; status: string; pnl: number | null; }

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-btn bg-surface p-3">
      <div className="text-[11px] text-muted">{label}</div>
      <div className="tabular mt-1 text-lg font-medium" style={{ color }}>{value}</div>
    </div>
  );
}

export default function BalancePage() {
  const [s, setS] = useState<Summary | null>(null);
  const [bets, setBets] = useState<Bet[] | null>(null);

  useEffect(() => {
    api.get<Summary>("/me/balance").then(setS).catch(() => {});
    api.get<Bet[]>("/me/bets").then(setBets).catch(() => {});
  }, []);

  return (
    <div>
      <header className="glass sticky top-0 z-10 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Mi saldo</h1>
      </header>

      <div className="p-4">
        <div className="rounded-card border border-border bg-surface p-5 text-center">
          <div className="text-xs text-muted">Saldo virtual</div>
          <div className="tabular mt-1 text-4xl font-semibold text-accent">{s ? eur(s.balance) : "—"}</div>
        </div>

        {!s ? <Skeleton className="mt-4 h-20" /> : (
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Stat label="Apuestas" value={`${s.n_bets}`} />
            <Stat label="Abiertas" value={`${s.n_open}`} />
            <Stat label="Ganadas / Perdidas" value={`${s.n_won} / ${s.n_lost}`} />
            <Stat label="P&L total" value={`${s.total_pnl >= 0 ? "+" : ""}${eur(s.total_pnl)}`} color={s.total_pnl >= 0 ? "var(--positive)" : "var(--negative)"} />
          </div>
        )}

        <h2 className="mb-2 mt-6 text-sm font-medium text-muted">Historial</h2>
        <div className="flex flex-col gap-2">
          {!bets && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
          {bets?.length === 0 && <p className="text-sm text-muted">Aún no has apostado.</p>}
          {bets?.filter((b) => b.decision !== "rejected").map((b) => (
            <div key={b.id} className="flex items-center justify-between rounded-card border border-border bg-surface p-3">
              <div>
                <div className="text-sm font-medium">{outcomeLabel(b.market, b.outcome)}</div>
                <div className="tabular text-xs text-muted">{eur(b.stake)} @ {fmtOdds(b.odds)} · {b.status}</div>
              </div>
              {b.pnl != null && (
                <span className="tabular text-sm font-medium" style={{ color: b.pnl >= 0 ? "var(--positive)" : "var(--negative)" }}>
                  {b.pnl >= 0 ? "+" : ""}{eur(b.pnl)}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
