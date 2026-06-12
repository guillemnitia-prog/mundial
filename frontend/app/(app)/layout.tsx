"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/useMe";
import { BottomTabBar } from "@/components/BottomTabBar";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { me, loading, error } = useMe();

  useEffect(() => {
    if (loading) return;
    if (error || !me) router.replace("/login");
    else if (!me.has_onboarded) router.replace("/onboarding");
  }, [me, loading, error, router]);

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
