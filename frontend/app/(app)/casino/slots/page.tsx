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

interface SpinResult { reels: string[]; multiplier: number; win: number; delta: number; balance: number; }

export default function SlotsPage() {
  const router = useRouter();
  const [balance, setBalance] = useState<number | null>(null);
  const [amount, setAmount] = useState("0.20");
  const [reels, setReels] = useState<string[]>(["🍒", "🍋", "🍊"]);
  const [spinning, setSpinning] = useState(false);
  const [last, setLast] = useState<SpinResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timers = useRef<any[]>([]);

  useEffect(() => {
    api.get<Me>("/auth/me").then((m) => setBalance(m.balance)).catch(() => {});
    return () => timers.current.forEach(clearInterval);
  }, []);

  const amt = parseFloat(amount.replace(",", "."));
  const valid = isFinite(amt) && amt >= 0.2 && balance != null && amt <= balance && !spinning;

  async function spin() {
    if (!valid) return;
    setSpinning(true); setErr(null); setLast(null);
    // Animación: cada rodillo cicla símbolos y se detiene escalonado.
    timers.current = [0, 1, 2].map((i) =>
      setInterval(() => {
        setReels((r) => {
          const n = [...r];
          n[i] = SYMBOLS[Math.floor(Math.random() * SYMBOLS.length)];
          return n;
        });
      }, 70)
    );
    try {
      const res = await api.post<SpinResult>("/casino/slots", { amount: amt });
      // Parar rodillos de izquierda a derecha, aterrizando en el resultado real.
      for (let i = 0; i < 3; i++) {
        await new Promise((r) => setTimeout(r, 500 + i * 350));
        clearInterval(timers.current[i]);
        setReels((cur) => { const n = [...cur]; n[i] = res.reels[i]; return n; });
      }
      setLast(res);
      setBalance(res.balance);
    } catch (e) {
      timers.current.forEach(clearInterval);
      setErr(e instanceof ApiError && e.detail === "invalid_amount" ? "Importe no válido (mín. 0,20 €, máx. tu saldo)." : "No se pudo jugar.");
    } finally {
      setSpinning(false);
    }
  }

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Slots Tropical</span>
        <span className="tabular ml-auto text-sm font-medium text-accent">{balance != null ? eur(balance) : "—"}</span>
      </header>

      <div className="p-4">
        {/* Máquina */}
        <div className="rounded-card border p-4" style={{ borderColor: "#FFB300", background: "linear-gradient(180deg,#0e3b4e,#0c2a20)" }}>
          <div className="mb-1 text-center text-[11px] font-semibold tracking-widest" style={{ color: "#FFB300" }}>
            🌴 SLOTS TROPICAL 🌴
          </div>
          <div className="grid grid-cols-3 gap-2">
            {reels.map((s, i) => (
              <div key={i} className="flex h-24 items-center justify-center rounded-xl border-2 bg-[#F5F5F5]"
                style={{ borderColor: "#14513c", boxShadow: "inset 0 -10px 18px rgba(0,0,0,0.18)" }}>
                <span className="text-5xl leading-none" style={{ filter: spinning ? "blur(1px)" : "none" }}>{s}</span>
              </div>
            ))}
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
          {spinning ? "Girando…" : "JUEGO"}
        </Press>

        {/* Tabla de premios */}
        <div className="mt-5 rounded-card border border-border bg-surface p-4">
          <div className="mb-2 text-sm font-medium" style={{ color: "#FFB300" }}>Premios (× tu apuesta)</div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1.5">
            {PAYTABLE.map(([s, m]) => (
              <div key={s} className="flex items-center justify-between rounded-md bg-bg px-2 py-1">
                <span className="text-base">{s}{s}{s}</span>
                <span className="tabular text-[12px] font-medium text-accent">x{m}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-muted">Dos iguales (cualquier par): x1,5 · Tres iguales: según símbolo</div>
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-[#737373]">
          Saldo virtual entre amigos. Resultado decidido en el servidor. +18 · juego responsable. Ninguna apuesta es segura.
        </p>
      </div>
    </div>
  );
}
