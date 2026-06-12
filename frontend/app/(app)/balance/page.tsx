"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { eur, odds as fmtOdds, outcomeLabel } from "@/lib/format";
import { pushPermission, subscribeToPush } from "@/lib/push";
import { Press, Skeleton } from "@/components/ui";

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
  const [perm, setPerm] = useState<string>("default");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  function reload() {
    api.get<Summary>("/me/balance").then(setS).catch(() => {});
  }

  useEffect(() => {
    reload();
    api.get<Bet[]>("/me/bets").then(setBets).catch(() => {});
    setPerm(pushPermission());
  }, []);

  async function enablePush() {
    const ok = await subscribeToPush();
    setPerm(ok ? "granted" : pushPermission());
  }

  async function adjust(kind: "deposit" | "withdraw" | "set") {
    const val = parseFloat(amount.replace(",", "."));
    if (!isFinite(val) || val < 0) { setErr("Importe no válido."); return; }
    setBusy(true); setErr(null);
    try {
      await api.post(`/me/balance/${kind}`, { amount: val });
      setAmount("");
      reload();
    } catch {
      setErr("No se pudo (revisa el importe / saldo).");
    } finally { setBusy(false); }
  }

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

        <div className="mt-4 rounded-card border border-border bg-surface p-4">
          <div className="mb-2 text-sm font-medium">Editar saldo</div>
          <input
            inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
            placeholder="Importe en €"
            className="tabular w-full rounded-btn border border-border bg-bg px-4 py-2.5 outline-none focus:border-accent"
          />
          <div className="mt-2 flex gap-2">
            <Press onClick={() => adjust("deposit")} className="flex-1 rounded-btn py-2 text-sm font-medium" style={{ background: "var(--accent)", color: "#0A1712" }}>
              {busy ? "…" : "Ingresar"}
            </Press>
            <Press onClick={() => adjust("withdraw")} className="flex-1 rounded-btn border border-border py-2 text-sm text-fg">Retirar</Press>
            <Press onClick={() => adjust("set")} className="flex-1 rounded-btn border border-border py-2 text-sm text-muted">Fijar</Press>
          </div>
          {err && <p className="mt-2 text-xs text-negative">{err}</p>}
          <p className="mt-2 text-[11px] text-[#737373]">Saldo virtual de partida: 50 €. Puedes ingresar, retirar o fijarlo cuando quieras.</p>
        </div>

        {perm === "unsupported" ? (
          <div className="mt-4 rounded-card border p-4" style={{ borderColor: "var(--warning)" }}>
            <div className="text-sm font-medium" style={{ color: "var(--warning)" }}>Activa las notificaciones</div>
            <div className="mt-1 text-xs leading-relaxed text-muted">
              En iPhone tienes que <span className="text-fg">instalar la app</span> primero:
              pulsa <span className="text-fg">Compartir</span> (el cuadrado con la flecha ↑) →
              <span className="text-fg"> "Añadir a pantalla de inicio"</span>. Luego abre la app
              <span className="text-fg"> desde ese icono</span> y vuelve aquí para activarlas.
            </div>
          </div>
        ) : perm !== "granted" ? (
          <div className="mt-4 flex items-center justify-between rounded-card border border-border bg-surface p-4">
            <div>
              <div className="text-sm font-medium">Notificaciones</div>
              <div className="text-xs text-muted">Avisos de apuestas y resultados</div>
            </div>
            <Press onClick={enablePush} className="rounded-btn px-4 py-2 text-sm font-medium" style={{ background: "var(--accent)", color: "#0A1712" }}>
              Activar
            </Press>
          </div>
        ) : null}

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
