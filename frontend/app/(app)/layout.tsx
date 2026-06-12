"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/useMe";
import { api } from "@/lib/api";
import { BottomTabBar } from "@/components/BottomTabBar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { me, loading, error } = useMe();

  useEffect(() => {
    if (loading) return;
    if (error || !me) router.replace("/login");
    else if (!me.has_onboarded) router.replace("/onboarding");
  }, [me, loading, error, router]);

  // Latido de presencia: marca "en línea" mientras la app esté abierta.
  useEffect(() => {
    if (!me?.has_onboarded) return;
    const ping = () => api.post("/me/ping").catch(() => {});
    ping();
    const t = setInterval(ping, 45000);
    return () => clearInterval(t);
  }, [me?.has_onboarded]);

  if (loading || !me) {
    return (
      <div className="app-shell flex items-center justify-center">
        <div className="text-muted">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      {children}
      <BottomTabBar />
    </div>
  );
}
