"use client";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { api, ApiError, Pick } from "@/lib/api";
import { eur, odds as fmtOdds, outcomeLabel, whyRecommendation } from "@/lib/format";
import { ConfidenceBadge, Press } from "./ui";

const MIN_STAKE = 10;

export function BetCard({
  pick, home, away, balance, locked, onChanged,
}: {
  pick: Pick; home?: string; away?: string; balance: number; locked: boolean;
  onChanged: (decision: string) => void;
}) {
  const [decision, setDecision] = useState<string | null>(pick.your_decision);
  const [sheet, setSheet] = useState(false);
  const [amount, setAmount] = useState<string>(pick.stake_eur.toFixed(2));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const profit = (pick.offered_odds - 1) * pick.stake_eur;
  const accent = pick.confidence === "alta";

  async function decide(action: string, custom?: number) {
    setBusy(true); setErr(null);
    try {
      await api.post(`/predictions/${pick.prediction_id}/decision`, { action, amount: custom });
      const d = action === "accept" ? "recommended" : action === "modify" ? "modified" : "rejected";
      setDecision(d); onChanged(d); setSheet(false);
    } catch (e) {
      setErr(e instanceof ApiError && e.detail === "invalid_amount" ? "Importe no válido (mín. 10 €)." : e instanceof ApiError && e.detail === "betting_locked" ? "Cerrado (faltan menos de 30 min)." : "No se pudo guardar.");
    } finally { setBusy(false); }
  }

  async function undo() {
    setBusy(true); setErr(null);
    try {
      await api.del(`/predictions/${pick.prediction_id}/decision`);
      setDecision(null); onChanged("");  // vuelve a sin-decisión: reaparecen los botones
    } catch (e) {
      setErr(e instanceof ApiError && e.detail === "betting_locked" ? "Cerrado (faltan menos de 30 min)." : "No se pudo deshacer.");
    } finally { setBusy(false); }
  }

  const custom = parseFloat(amount.replace(",", "."));
  const customPct = balance > 0 ? (custom / balance) * 100 : 0;
  const customProfit = (pick.offered_odds - 1) * (isFinite(custom) ? custom : 0);
  const validCustom = isFinite(custom) && custom >= MIN_STAKE && custom <= balance;

  const DEC_LABEL: Record<string, string> = {
    recommended: "Aceptada", modified: "Importe cambiado", rejected: "Rechazada", default: "Por defecto",
  };

  return (
    <div className="mx-4 mb-3 rounded-card border bg-surface p-4" style={{ borderColor: accent ? "var(--accent)" : "var(--border)" }}>
      <div className="mb-2 flex items-center gap-2">
        <span className="text-[15px] font-medium">{outcomeLabel(pick.market, pick.outcome, home, away)}</span>
        <ConfidenceBadge confidence={pick.confidence} />
        <span className="tabular ml-auto text-base font-medium">{fmtOdds(pick.offered_odds)}</span>
      </div>

      {/* Modelo vs mercado, visual */}
      <div className="mb-3 space-y-1.5">
        <div className="flex items-center gap-2 text-[11px]">
          <span className="w-14 text-muted">Modelo</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
            <div className="h-full bg-accent" style={{ width: `${Math.round(pick.model_prob * 100)}%` }} />
          </div>
          <span className="tabular w-8 text-right font-medium">{Math.round(pick.model_prob * 100)}%</span>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <span className="w-14 text-muted">Mercado</span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-border">
            <div className="h-full" style={{ width: `${Math.round(pick.fair_prob * 100)}%`, background: "#525252" }} />
          </div>
          <span className="tabular w-8 text-right text-muted">{Math.round(pick.fair_prob * 100)}%</span>
        </div>
      </div>

      {/* Por qué la recomendación */}
      <div className="mb-3 rounded-[10px] border border-border bg-bg p-2.5">
        <div className="mb-1 flex items-center gap-1.5 text-[11px] font-medium text-accent">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          Por qué
        </div>
        <p className="text-[12px] leading-relaxed text-muted">
          {whyRecommendation(pick.market, pick.outcome, pick.model_prob, pick.fair_prob, pick.ev_pct, pick.confidence, home, away)}
        </p>
        <div className="mt-1.5 flex gap-3 text-[11px]">
          <span className="text-muted">Cuota <span className="tabular font-medium text-fg">{fmtOdds(pick.offered_odds)}</span></span>
          <span className="text-muted">EV <span className="tabular font-medium text-positive">+{pick.ev_pct}%</span></span>
        </div>
      </div>

      <div className="mb-3 rounded-[10px] px-3 py-2 text-[13px]" style={{ background: "var(--accent-faint)" }}>
        Apuesta <span className="tabular font-medium text-accent">{eur(pick.stake_eur)}</span>
        <span className="text-muted"> — {pick.stake_pct}% de tu saldo · beneficio +{eur(profit)}</span>
      </div>

      {decision ? (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted">Tu decisión: <span className="font-medium text-fg">{DEC_LABEL[decision]}</span></span>
          {!locked && (
            <span className="flex gap-3">
              {decision !== "rejected" && <button className="text-accent" onClick={() => setSheet(true)}>Cambiar</button>}
              <button className="text-muted" onClick={undo}>{busy ? "…" : "Deshacer"}</button>
            </span>
          )}
        </div>
      ) : locked ? (
        <p className="text-sm text-muted">Cerrado (faltan menos de 30 min).</p>
      ) : (
        <div className="flex gap-2">
          <Press onClick={() => decide("accept")} className="flex-1 rounded-btn py-2.5 text-[13px] font-medium" style={{ background: "var(--accent)", color: "#0A0A0A" }}>
            {busy ? "…" : "Aceptar"}
          </Press>
          <Press onClick={() => setSheet(true)} className="flex-1 rounded-btn border border-border py-2.5 text-[13px] text-fg">Cambiar</Press>
          <Press onClick={() => decide("reject")} className="rounded-btn border border-border px-3 py-2.5 text-[13px] text-muted">Rechazar</Press>
        </div>
      )}
      {err && <p className="mt-2 text-xs text-negative">{err}</p>}

      <AnimatePresence>
        {sheet && (
          <motion.div
            className="fixed inset-0 z-50 flex items-end justify-center"
            style={{ background: "rgba(0,0,0,0.55)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setSheet(false)}
          >
            <motion.div
              className="w-full max-w-[430px] rounded-t-3xl border-t border-border bg-surface p-5"
              style={{ paddingBottom: "calc(20px + env(safe-area-inset-bottom))" }}
              initial={{ y: 300 }} animate={{ y: 0 }} exit={{ y: 300 }} transition={{ duration: 0.22 }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-border" />
              <h3 className="text-base font-medium">Cambiar importe</h3>
              <p className="mt-1 text-xs text-muted">Mín. {eur(MIN_STAKE)} · máx. tu saldo {eur(balance)}</p>
              <input
                inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="tabular mt-4 w-full rounded-btn border border-border bg-bg px-4 py-3 text-lg outline-none focus:border-accent"
              />
              <div className="mt-3 flex justify-between text-sm">
                <span className="text-muted">{isFinite(customPct) ? `${customPct.toFixed(1)}% de tu saldo` : "—"}</span>
                <span className="text-muted">Beneficio potencial <span className="tabular text-positive">+{eur(isFinite(customProfit) ? customProfit : 0)}</span></span>
              </div>
              <Press
                onClick={() => validCustom && decide("modify", Math.round(custom * 100) / 100)}
                className="mt-5 w-full rounded-btn py-3 font-medium disabled:opacity-40"
                style={{ background: validCustom ? "var(--accent)" : "#262626", color: validCustom ? "#0A0A0A" : "#737373" }}
              >
                {busy ? "Guardando…" : "Confirmar apuesta"}
              </Press>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
