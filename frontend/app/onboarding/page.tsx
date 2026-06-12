"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Press, Skeleton } from "@/components/ui";

interface Team { id: number; name: string; fifa_code: string | null; }
interface Status { has_onboarded: boolean; teams: Team[]; }

export default function OnboardingPage() {
  const router = useRouter();
  const [teams, setTeams] = useState<Team[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get<Status>("/onboarding").then((s) => {
      if (s.has_onboarded) router.replace("/matches");
      else setTeams(s.teams);
    }).catch(() => router.replace("/login"));
  }, [router]);

  async function confirm() {
    if (selected == null) return;
    setBusy(true);
    try {
      await api.post("/onboarding/champion", { team_id: selected });
      router.replace("/matches");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell px-5 pt-8" style={{ paddingBottom: "120px" }}>
      <h1 className="text-xl font-medium">¿Quién ganará el Mundial?</h1>
      <p className="mt-1 text-sm text-muted">Elige tu campeón. Es obligatorio y no se puede cambiar.</p>

      <div className="mt-6 grid grid-cols-2 gap-2">
        {!teams && Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}
        {teams?.map((t) => (
          <button
            key={t.id}
            onClick={() => setSelected(t.id)}
            className="rounded-btn border px-3 py-3 text-left text-sm"
            style={{
              borderColor: selected === t.id ? "var(--accent)" : "var(--border)",
              background: selected === t.id ? "var(--accent-faint)" : "var(--surface)",
            }}
          >
            <span className="text-muted">{t.fifa_code}</span> · {t.name}
          </button>
        ))}
      </div>

      <div className="fixed bottom-0 left-1/2 w-full max-w-[430px] -translate-x-1/2 glass border-t border-border p-4" style={{ paddingBottom: "calc(16px + env(safe-area-inset-bottom))" }}>
        <Press
          onClick={confirm}
          className="w-full rounded-btn py-3 font-medium disabled:opacity-40"
          style={{ background: "var(--accent)", color: "#0A0A0A" }}
        >
          {busy ? "Guardando…" : selected ? "Confirmar campeón" : "Selecciona un equipo"}
        </Press>
      </div>
    </div>
  );
}
