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
    api.get<MatchDetail>(`/matches/${id}`).then(setM).catch(() => {});
    api.get<Me>("/auth/me").then((me) => setBalance(me.balance)).catch(() => {});
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
                      <div className="mt-1 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: "#FF5252", color: "#0A0A0A" }}>
                        <span className="h-1.5 w-1.5 rounded-full bg-[#0A0A0A] animate-pulse" /> EN VIVO
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

          <Disclaimer />
        </>
      )}
    </div>
  );
}
