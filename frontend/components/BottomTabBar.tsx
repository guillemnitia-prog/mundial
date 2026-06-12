"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/matches", label: "Partidos", icon: "M4 5h16M4 12h16M4 19h10" },
  { href: "/casino", label: "Casino", icon: "M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zM8 8h.01M16 16h.01M12 12h.01" },
  { href: "/balance", label: "Mi saldo", icon: "M3 7h18v10H3zM3 11h18" },
  { href: "/ranking", label: "Ranking", icon: "M6 21V9m6 12V3m6 18v-7" },
  { href: "/chat", label: "Chat", icon: "M4 5h16v11H8l-4 4z" },
];

export function BottomTabBar() {
  const path = usePathname();
  return (
    <nav
      className="glass fixed bottom-0 left-1/2 w-full max-w-[430px] -translate-x-1/2 border-t border-border"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <div className="flex">
        {TABS.map((t) => {
          const active = path.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className="flex flex-1 flex-col items-center gap-1 py-3"
              style={{ color: active ? "var(--accent)" : "var(--text-secondary)" }}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d={t.icon} />
              </svg>
              <span className="text-[10px]">{t.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
