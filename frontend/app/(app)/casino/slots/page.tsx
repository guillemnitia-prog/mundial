"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Me } from "@/lib/api";
import { eur } from "@/lib/format";
import { Press } from "@/components/ui";

const SYMBOLS = ["🍒", "🍋", "🍊", "🍓", "🍉", "⭐", "🔶", "🔷", "💎"];
const PAYTABLE: Array<[string, number]> = [
  ["💎", 1000], ["🔷", 200], ["🔶", 100], ["⭐", 40],
  ["🍉", 24], ["🍓", 16], ["🍊", 12], ["🍋", 8], ["🍒", 4],
];
const rand = () => SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];

interface SpinResult {
  columns: string[][]; payline: string[]; multiplier: number;
  win: number; delta: number; casino_balance: number;
}

export default function SlotsPage() {
  const router = useRouter();
  const [balance, setBalance] = useState<number | null>(null);
  const [amount, setAmount] = useState("0.20");
  // columns[i] = [arriba, centro, abajo] del rodillo i.
  const [cols, setCols] = useState<string[][]>([["🍒", "🍋", "🍊"], ["🍉", "⭐", "🍓"], ["🍊", "💎", "🍒"]]);
  const [spinning, setSpinning] = useState<boolean[]>([false, false, false]);
  const [last, setLast] = useState<SpinResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timers = useRef<any[]>([]);

  useEffect(() => {
    api.get<Me>("/auth/me").then((m) => setBalance(m.casino_balance)).catch(() => {});
    return () => timers.current.forEach(clearInterval);
  }, []);

  const amt = parseFloat(amount.replace(",", "."));
  const busy = spinning.some(Boolean);
  const valid = isFinite(amt) && amt >= 0.2 && balance != null && amt <= balance && !busy;

  async function spin() {
    if (!valid) return;
    setErr(null); setLast(null);
    setSpinning([true, true, true]);
    // Caída: cada rodillo desplaza símbolos hacia abajo (entra uno nuevo por arriba).
    timers.current = [0, 1, 2].map((i) =>
      setInterval(() => {
        setCols((c) => {
          const n = c.map((col) => [...col]);
          n[i] = [rand(), n[i][0], n[i][1]];
          return n;
        });
      }, 75)
    );
    try {
      const res = await api.post<SpinResult>("/casino/slots", { amount: amt });
      // Parar rodillos de izquierda a derecha aterrizando en la columna real.
      for (let i = 0; i < 3; i++) {
        await new Promise((r) => setTimeout(r, 550 + i * 400));
        clearInterval(timers.current[i]);
        setCols((c) => { const n = c.map((col) => [...col]); n[i] = res.columns[i]; return n; });
        setSpinning((s) => { const n = [...s]; n[i] = false; return n; });
      }
      setLast(res);
      setBalance(res.casino_balance);
    } catch (e) {
      timers.current.forEach(clearInterval);
      setSpinning([false, false, false]);
      setErr(e instanceof ApiError && e.detail === "invalid_amount" ? "Importe no válido (mín. 0,20 €, máx. tu saldo de casino)." : "No se pudo jugar.");
    }
  }

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Slots Tropical</span>
        <span className="tabular ml-auto rounded-full px-2.5 py-1 text-sm font-semibold" style={{ background: "#FFB30022", color: "#FFB300" }}>
          🎰 {balance != null ? eur(balance) : "—"}
        </span>
      </header>

      <div className="p-4">
        {/* Máquina 3x3 */}
        <div className="rounded-card border p-4" style={{ borderColor: "#FFB300", background: "linear-gradient(180deg,#0e3b4e,#0c2a20)" }}>
          <div className="mb-2 text-center text-[11px] font-semibold tracking-widest" style={{ color: "#FFB300" }}>
            🌴 SLOTS TROPICAL 🌴
          </div>
          <div className="relative">
            <div className="grid grid-cols-3 gap-2">
              {cols.map((col, i) => (
                <div key={i} className="overflow-hidden rounded-xl border-2 bg-[#F5F5F5]" style={{ borderColor: "#14513c" }}>
                  {col.map((s, row) => (
                    <div key={row}
                      className="flex h-16 items-center justify-center"
                      style={{
                        background: row === 1 ? "#fffbe8" : "#F5F5F5",
                        borderTop: row > 0 ? "1px dashed #d8d2bd" : "none",
                        opacity: spinning[i] ? 0.85 : row === 1 ? 1 : 0.55,
                      }}>
                      <span className="text-4xl leading-none" style={{ filter: spinning[i] ? "blur(1.5px)" : "none" }}>{s}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
            {/* Línea de premio (central) */}
            <div className="pointer-events-none absolute left-[-6px] right-[-6px] top-1/2 z-10 -translate-y-1/2">
              <div className="h-[2px] w-full" style={{ background: "#FFB300", boxShadow: "0 0 6px #FFB300" }} />
            </div>
            <span className="pointer-events-none absolute left-[-4px] top-1/2 z-10 -translate-y-1/2 -translate-x-full pr-1 text-[9px] font-semibold" style={{ color: "#FFB300", writingMode: "vertical-rl", textOrientation: "mixed" }}>
              LÍNEA
            </span>
          </div>
          <div className="mt-2 h-6 text-center text-sm">
            {last && (
              last.win > 0 ? (
                <span className="font-semibold" style={{ color: "var(--positive)" }}>
                  {last.multiplier >= 4 ? "🎉 ¡TRES IGUALES! " : "¡Pareja! "}+{eur(last.win)} (x{last.multiplier})
                </span>
              ) : (
                <span className="text-muted">Sin premio… ¡otra vez!</span>
              )
            )}
          </div>
        </div>

        {/* Apuesta */}
        <div className="mt-4 flex items-center gap-2">
          {["0.20", "0.50", "1", "2", "5"].map((v) => (
            <button key={v} onClick={() => setAmount(v)}
              className="flex-1 rounded-btn border py-2 text-sm"
              style={{ borderColor: amount === v ? "#FFB300" : "var(--border)", color: amount === v ? "#FFB300" : "var(--text-secondary)" }}>
              {v.replace(".", ",")} €
            </button>
          ))}
        </div>
        <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal"
          className="tabular mt-2 w-full rounded-btn border border-border bg-bg px-4 py-2.5 text-base outline-none focus:border-accent" />

        {err && <p className="mt-2 text-sm text-negative">{err}</p>}
        <Press onClick={spin} className="mt-3 w-full rounded-btn py-3.5 text-base font-semibold disabled:opacity-40"
          style={{ background: valid ? "var(--accent)" : "#20392C", color: valid ? "#0A1712" : "#737373" }}>
          {busy ? "Girando…" : "JUEGO"}
        </Press>

        <p className="mt-2 text-center text-[11px] text-muted">
          Se juega con tu <span style={{ color: "#FFB300" }}>saldo de casino</span> (20 € de regalo) — no afecta a tu saldo de apuestas.
        </p>

        {/* Tabla de premios */}
        <div className="mt-4 rounded-card border border-border bg-surface p-4">
          <div className="mb-2 text-sm font-medium" style={{ color: "#FFB300" }}>Premios en la línea central (× tu apuesta)</div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5">
            {PAYTABLE.map(([s, m]) => (
              <div key={s} className="flex items-center justify-between rounded-md bg-bg px-2 py-1">
                <span className="text-base">{s}{s}{s}</span>
                <span className="tabular text-[12px] font-medium text-accent">x{m}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-muted">Dos iguales en la línea: x1,5 · Tres iguales: según símbolo</div>
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-[#737373]">
          Saldo virtual entre amigos. Resultado decidido en el servidor. +18 · juego responsable. Ninguna apuesta es segura.
        </p>
      </div>
    </div>
  );
}
