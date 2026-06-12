"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Me } from "@/lib/api";
import { eur } from "@/lib/format";
import { Press } from "@/components/ui";

const RED = new Set([1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36]);
const colorOf = (n: number) => (n === 0 ? "#00E676" : RED.has(n) ? "#FF5252" : "#262626");

interface SpinResult { result: number; color: string; won: boolean; delta: number; balance: number; }

export default function RuletaPage() {
  const router = useRouter();
  const [balance, setBalance] = useState<number | null>(null);
  const [amount, setAmount] = useState("5");
  const [pick, setPick] = useState<{ type: "color" | "number"; sel: string | number }>({ type: "color", sel: "red" });
  const [num, setNum] = useState("");
  const [spinning, setSpinning] = useState(false);
  const [display, setDisplay] = useState<number>(0);
  const [last, setLast] = useState<SpinResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<any>(null);

  useEffect(() => {
    api.get<Me>("/auth/me").then((m) => setBalance(m.balance)).catch(() => {});
    return () => clearInterval(timer.current);
  }, []);

  const amt = parseFloat(amount.replace(",", "."));
  const valid = isFinite(amt) && amt >= 1 && balance != null && amt <= balance && !spinning;

  async function spin() {
    if (!valid) return;
    setSpinning(true); setErr(null); setLast(null);
    // Animación: números cambiando rápido.
    timer.current = setInterval(() => setDisplay(Math.floor(Math.random() * 37)), 70);
    try {
      const selection = pick.type === "number" ? Number(num) : pick.sel;
      const res = await api.post<SpinResult>("/casino/roulette", { bet_type: pick.type, selection, amount: amt });
      // Dejar girar ~1.4s y aterrizar en el resultado real.
      await new Promise((r) => setTimeout(r, 1400));
      clearInterval(timer.current);
      setDisplay(res.result);
      setLast(res);
      setBalance(res.balance);
    } catch (e) {
      clearInterval(timer.current);
      setErr(e instanceof ApiError && e.detail === "invalid_amount" ? "Importe no válido (mín. 1 €, máx. tu saldo)." : "No se pudo jugar.");
    } finally {
      setSpinning(false);
    }
  }

  const ColorBtn = ({ sel, label, bg }: { sel: string; label: string; bg: string }) => {
    const active = pick.type === "color" && pick.sel === sel;
    return (
      <button onClick={() => setPick({ type: "color", sel })}
        className="flex-1 rounded-btn py-3 text-sm font-medium"
        style={{ background: bg, color: sel === "black" ? "#F5F5F5" : "#0A0A0A", outline: active ? "2px solid #FFB300" : "none" }}>
        {label}
      </button>
    );
  };

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Ruleta</span>
        <span className="tabular ml-auto text-sm font-medium text-accent">{balance != null ? eur(balance) : "—"}</span>
      </header>

      <div className="p-4">
        {/* Rueda / resultado */}
        <div className="mb-5 flex flex-col items-center rounded-card p-6" style={{ background: "#0c2a20", border: "1px solid #14513c" }}>
          <div className="flex h-28 w-28 items-center justify-center rounded-full border-4" style={{ borderColor: "#FFB300", background: colorOf(display) }}>
            <span className="tabular text-4xl font-bold" style={{ color: display === 0 || RED.has(display) ? "#0A0A0A" : "#F5F5F5" }}>{display}</span>
          </div>
          <div className="mt-3 h-5 text-sm">
            {last && (
              <span className="font-medium" style={{ color: last.won ? "var(--positive)" : "var(--negative)" }}>
                {last.won ? `¡Ganaste +${eur(last.delta)}!` : `Perdiste ${eur(-last.delta)}`}
              </span>
            )}
          </div>
        </div>

        {/* Apuesta */}
        <div className="mb-2 text-sm font-medium text-muted">Tu apuesta</div>
        <div className="mb-3 flex gap-2">
          <ColorBtn sel="red" label="Rojo (x2)" bg="#FF5252" />
          <ColorBtn sel="black" label="Negro (x2)" bg="#262626" />
          <ColorBtn sel="green" label="0 (x36)" bg="#00E676" />
        </div>
        <div className="mb-4 flex items-center gap-2">
          <input value={num} onChange={(e) => { setNum(e.target.value); setPick({ type: "number", sel: Number(e.target.value) }); }}
            inputMode="numeric" placeholder="Pleno 0-36 (x36)"
            className="tabular flex-1 rounded-btn border px-4 py-2.5 outline-none"
            style={{ background: "var(--bg)", borderColor: pick.type === "number" ? "#FFB300" : "var(--border)" }} />
        </div>

        <div className="mb-2 text-sm font-medium text-muted">Importe</div>
        <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal"
          className="tabular mb-2 w-full rounded-btn border border-border bg-bg px-4 py-3 text-lg outline-none focus:border-accent" />
        <div className="mb-4 flex gap-2">
          {[1, 5, 10, 25].map((v) => (
            <button key={v} onClick={() => setAmount(String(v))} className="flex-1 rounded-btn border border-border py-1.5 text-sm text-muted">{v} €</button>
          ))}
        </div>

        {err && <p className="mb-2 text-sm text-negative">{err}</p>}
        <Press onClick={spin} className="w-full rounded-btn py-3.5 text-base font-semibold disabled:opacity-40"
          style={{ background: valid ? "var(--accent)" : "#262626", color: valid ? "#0A0A0A" : "#737373" }}>
          {spinning ? "Girando…" : "Girar"}
        </Press>

        <p className="mt-4 text-[11px] leading-relaxed text-[#737373]">
          Saldo virtual entre amigos. Ruleta europea (un solo 0). +18 · juego responsable. Ninguna apuesta es segura.
        </p>
      </div>
    </div>
  );
}
