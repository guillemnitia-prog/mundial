"use client";
import { useEffect, useRef, useState } from "react";
import { WS_BASE, Me, api } from "@/lib/api";

interface Msg { username: string; content: string; created_at: string; }

export default function ChatPage() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [me, setMe] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let closed = false;
    api.get<Me>("/auth/me").then((m) => setMe(m.username)).catch(() => {});
    // Pide un token (la cookie httpOnly no la lee JS) y conecta el WS directo al backend.
    api.get<{ token: string }>("/auth/ws-token").then(({ token }) => {
      if (closed) return;
      ws = new WebSocket(`${WS_BASE}/ws/chat?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;
      ws.onopen = () => setConnected(true);
      ws.onclose = () => setConnected(false);
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "history") setMsgs(data.messages);
        else if (data.type === "message") setMsgs((prev) => [...prev, data]);
      };
    }).catch(() => {});
    return () => { closed = true; ws?.close(); };
  }, []);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  function send() {
    const t = text.trim();
    if (!t || wsRef.current?.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(t);
    setText("");
  }

  return (
    // Caja fija entre la cabecera y la barra inferior: SOLO la conversación hace scroll.
    <div className="fixed left-1/2 top-0 z-0 flex w-full max-w-[430px] -translate-x-1/2 flex-col"
      style={{ bottom: "calc(60px + env(safe-area-inset-bottom))" }}>
      <header className="glass z-10 flex shrink-0 items-center gap-2 border-b border-border px-4 py-3" style={{ paddingTop: "calc(12px + env(safe-area-inset-top))" }}>
        <h1 className="text-lg font-medium">Chat</h1>
        <span className="ml-auto text-xs" style={{ color: connected ? "var(--positive)" : "var(--muted)" }}>
          {connected ? "● en línea" : "conectando…"}
        </span>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
        {msgs.map((m, i) => {
          const mine = m.username === me;
          return (
            <div key={i} className={`mb-2 flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className="max-w-[78%] rounded-2xl px-3 py-2" style={{ background: mine ? "var(--accent)" : "var(--surface)", color: mine ? "#0A1712" : "var(--text)" }}>
                {!mine && <div className="text-[11px] font-medium text-accent">{m.username}</div>}
                <div className="text-sm">{m.content}</div>
                <div className="mt-0.5 text-[10px]" style={{ color: mine ? "#0A171299" : "var(--text-secondary)" }}>
                  {new Date(m.created_at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
                </div>
              </div>
            </div>
          );
        })}
        <div ref={endRef} />
      </div>

      <div className="flex shrink-0 gap-2 border-t border-border p-3" style={{ background: "#0a120e" }}>
        <input
          value={text} onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Mensaje…"
          className="flex-1 rounded-btn border border-border bg-surface px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <button onClick={send} className="rounded-btn px-4 font-medium" style={{ background: "var(--accent)", color: "#0A1712" }}>Enviar</button>
      </div>
    </div>
  );
}
