"use client";
import { useEffect, useState } from "react";
import { api, Me } from "@/lib/api";
import { eur } from "@/lib/format";
import { Skeleton } from "@/components/ui";

interface Row { username: string; balance: number; }

export default function RankingPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [me, setMe] = useState<string | null>(null);

  useEffect(() => {
    api.get<Row[]>("/ranking").then(setRows).catch(() => {});
    api.get<Me>("/auth/me").then((m) => setMe(m.username)).catch(() => {});
  }, []);

  return (
    <div>
      <header className="glass sticky top-0 z-10 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Ranking del grupo</h1>
      </header>

      <div className="flex flex-col gap-2 p-4">
        {!rows && Array.from({ length: 7 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
        {rows?.map((r, i) => {
          const mine = r.username === me;
          return (
            <div key={r.username} className="flex items-center gap-3 rounded-card border p-3"
              style={{ borderColor: mine ? "var(--accent)" : "var(--border)", background: mine ? "var(--accent-faint)" : "var(--surface)" }}>
              <span className="tabular w-6 text-center text-sm font-medium" style={{ color: i === 0 ? "var(--accent)" : "var(--muted)" }}>{i + 1}</span>
              <span className="flex-1 text-sm font-medium">{r.username}{mine && " (tú)"}</span>
              <span className="tabular text-sm font-medium">{eur(r.balance)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
