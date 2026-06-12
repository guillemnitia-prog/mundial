"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, MatchDetail, Me } from "@/lib/api";
import { matchDate, timeAgo } from "@/lib/format";
import { BetCard } from "@/components/BetCard";
import { Disclaimer, FormDots, Skeleton, StateChip } from "@/components/ui";

function TeamCol({ t }: { t: MatchDetail["home"] }) {
  return (
    <div className="w-[38%] text-center">
      <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full border border-border bg-surface text-sm font-medium">
        {t?.fifa_code ?? "?"}
      </div>
      <div className="text-sm font-medium">{t?.name ?? "Por definir"}{t?.is_host && " 🏟"}</div>
      <div className="tabular text-xs text-muted">{t?.elo ? `Elo ${Math.round(t.elo)}` : "—"}</div>
    </div>
  );
}

export default function MatchDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [m, setM] = useState<MatchDetail | null>(null);
  const [balance, setBalance] = useState(0);

  useEffect(() => {
    const load = () => api.get<MatchDetail>(`/matches/${id}`).then(setM).catch(() => {});
    load();
    api.get<Me>("/auth/me").then((me) => setBalance(me.balance)).catch(() => {});
    // Si el partido está en vivo, refresca el marcador cada 20 s.
    const t = setInterval(() => {
      setM((cur) => { if (cur?.state === "en vivo") load(); return cur; });
    }, 20000);
    return () => clearInterval(t);
  }, [id]);

  // Bloqueo: en vivo/finalizado, o a menos de 30 min del inicio.
  const within30 = !!m?.utc_date && Date.now() > new Date(m.utc_date).getTime() - 30 * 60 * 1000;
  const locked = m?.state === "en vivo" || m?.state === "finalizado" || within30;

  return (
    <div>
      <header className="glass sticky top-0 z-10 flex items-center gap-3 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <button onClick={() => router.back()} aria-label="Volver" className="text-muted">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[15px] font-medium">Detalle del partido</span>
        {m && <span className="ml-auto"><StateChip state={m.state} /></span>}
      </header>

      {!m ? (
        <div className="flex flex-col gap-3 p-4">
          <Skeleton className="h-28" /><Skeleton className="h-24" /><Skeleton className="h-40" />
        </div>
      ) : (
        <>
          <div className="px-4 pb-2 pt-5">
            <div className="flex items-center justify-between">
              <TeamCol t={m.home} />
              <div className="text-center">
                {(m.status === "live" || m.status === "finished") && m.home_goals != null && m.away_goals != null ? (
                  <>
                    <div className="tabular text-3xl font-semibold">
                      {m.home_goals} <span className="text-muted">-</span> {m.away_goals}
                    </div>
                    {m.status === "live" ? (
                      <div className="mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: "#FF5252", color: "#0A1712" }}>
                        <span className="h-1.5 w-1.5 rounded-full bg-[#0A1712] animate-pulse" /> EN VIVO
                      </div>
                    ) : (
                      <div className="mt-1 text-[11px] text-muted">Finalizado</div>
                    )}
                  </>
                ) : (
                  <>
                    <div className="text-xs text-muted">{matchDate(m.utc_date)}</div>
                    <div className="my-1 text-lg font-medium text-muted">vs</div>
                  </>
                )}
                <div className="mt-1 text-[11px] text-muted">
                  {m.stage === "group" ? `Grupo ${m.group_label ?? ""}` : m.stage} · {m.neutral_venue ? "campo neutral" : "con anfitrión"}
                </div>
              </div>
              <TeamCol t={m.away} />
            </div>

            <div className="mt-3 flex justify-center gap-5 text-[11px] text-muted">
              <span className="flex items-center gap-1">{m.home?.name}: <FormDots form={m.home_form} /></span>
              <span className="flex items-center gap-1">{m.away?.name}: <FormDots form={m.away_form} /></span>
            </div>
            {m.analyzed_at && (
              <div className="mt-2 text-center text-[11px] text-[#737373]">
                Actualizado {timeAgo(m.analyzed_at)} · análisis {m.analysis_stage === "final" ? "final" : "preliminar"}
              </div>
            )}
          </div>

          {m.stats?.x1x2 && (
            <div className="mx-4 mt-3 rounded-card border border-border bg-surface p-4">
              <div className="mb-2 text-sm font-medium">Estadísticas del modelo</div>
              <div className="mb-1 flex h-3 overflow-hidden rounded-full">
                <div style={{ width: `${Math.round(m.stats.x1x2.home * 100)}%`, background: "var(--accent)" }} />
                <div style={{ width: `${Math.round(m.stats.x1x2.draw * 100)}%`, background: "#3a5a4a" }} />
                <div style={{ width: `${Math.round(m.stats.x1x2.away * 100)}%`, background: "#2f6f4f" }} />
              </div>
              <div className="tabular flex justify-between text-[11px] text-muted">
                <span>{m.home?.name} <span className="font-medium text-fg">{Math.round(m.stats.x1x2.home * 100)}%</span></span>
                <span>X <span className="font-medium text-fg">{Math.round(m.stats.x1x2.draw * 100)}%</span></span>
                <span><span className="font-medium text-fg">{Math.round(m.stats.x1x2.away * 100)}%</span> {m.away?.name}</span>
              </div>
              {(m.stats.over25 != null || m.stats.btts_yes != null) && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {m.stats.over25 != null && (
                    <div className="rounded-btn bg-bg p-2 text-center">
                      <div className="text-[10px] text-muted">Más de 2.5 goles</div>
                      <div className="tabular text-base font-medium text-accent">{Math.round(m.stats.over25 * 100)}%</div>
                    </div>
                  )}
                  {m.stats.btts_yes != null && (
                    <div className="rounded-btn bg-bg p-2 text-center">
                      <div className="text-[10px] text-muted">Ambos marcan</div>
                      <div className="tabular text-base font-medium text-accent">{Math.round(m.stats.btts_yes * 100)}%</div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="mb-1 mt-3 px-4 text-sm font-medium text-muted">
            {m.picks.length > 0 ? `Apuestas de valor (${m.picks.length})` : "Análisis"}
          </div>

          {m.message ? (
            <div className="mx-4 mb-3 rounded-card border border-border bg-surface p-5 text-center text-sm text-muted">
              {m.message}
            </div>
          ) : (
            m.picks.map((p) => (
              <BetCard
                key={p.prediction_id} pick={p} home={m.home?.name} away={m.away?.name}
                balance={balance} locked={!!locked} onChanged={() => {}}
              />
            ))
          )}

          <button onClick={() => router.push("/como-funciona")}
            className="mx-4 mb-1 mt-2 flex w-[calc(100%-2rem)] items-center justify-center gap-2 rounded-btn border border-border py-2.5 text-sm text-accent">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
            Cómo se calculan estas probabilidades
          </button>
          <Disclaimer />
        </>
      )}
    </div>
  );
}
