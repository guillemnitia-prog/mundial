"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, Me } from "@/lib/api";
import { Press } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const me = await api.post<Me>("/auth/login", { username, password });
      router.replace(me.has_onboarded ? "/matches" : "/onboarding");
    } catch (e) {
      setError(e instanceof ApiError && e.detail === "invalid_credentials" ? "Usuario o contraseña incorrectos." : "No se pudo iniciar sesión.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell flex flex-col justify-center px-6" style={{ paddingBottom: 0 }}>
      <div className="mb-10 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full border-2" style={{ borderColor: "var(--accent)" }}>
          <span className="text-2xl font-semibold text-accent">€</span>
        </div>
        <h1 className="text-xl font-medium">WorldCup Betting</h1>
        <p className="mt-1 text-sm text-muted">Análisis de valor · grupo privado</p>
      </div>

      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          className="rounded-btn border border-border bg-surface px-4 py-3 text-fg outline-none focus:border-accent"
          placeholder="Usuario" value={username} onChange={(e) => setUsername(e.target.value)} autoCapitalize="none"
        />
        <input
          type="password"
          className="rounded-btn border border-border bg-surface px-4 py-3 text-fg outline-none focus:border-accent"
          placeholder="Contraseña" value={password} onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="text-sm text-negative">{error}</p>}
        <Press
          className="mt-2 rounded-btn py-3 font-medium disabled:opacity-50"
          style={{ background: "var(--accent)", color: "#0A1712" }}
        >
          {busy ? "Entrando…" : "Entrar"}
        </Press>
      </form>

      <p className="mt-8 text-center text-[11px] leading-relaxed text-[#737373]">
        Acceso solo para los 7 miembros. +18 · juego responsable.
      </p>
    </div>
  );
}
