"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useMe } from "@/lib/useMe";

export default function Home() {
  const router = useRouter();
  const { me, loading, error } = useMe();

  useEffect(() => {
    if (loading) return;
    if (error || !me) router.replace("/login");
    else if (!me.has_onboarded) router.replace("/onboarding");
    else router.replace("/matches");
  }, [me, loading, error, router]);

  return (
    <div className="app-shell flex items-center justify-center">
      <div className="text-muted">Cargando…</div>
    </div>
  );
}
