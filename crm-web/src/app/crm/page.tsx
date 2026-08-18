"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Lead = {
  phone: string;
  name: string;
  stage: string;
  etapa_seg: string;
  prox_seg_ts: string;
  last_message: string;
  paused: boolean;
  status: string;
  cualificado: string;
  razon_no_cual: string;
};

type Msg = { id: string; direction: string; text: string; ts: string; actor?: string };
type Event = { id: string; step: string; ts: string; actor?: string };
type Notification = { id: number; phone: string; tipo: string; titulo: string; detalle: string; read_at: string | null; created_at: string };

const STEP_LABELS: Record<string, string> = {
  bienvenida: "Bienvenida m1/m2",
  q1: "Wizard Q1",
  q2: "Wizard Q2",
  q3: "Wizard Q3",
  q4: "Wizard Q4",
  q5: "Wizard Q5",
  q6: "Wizard Q6",
  q7: "Wizard Q7",
  q8: "Wizard Q8",
  q9: "Wizard Q9",
  cualificado: "Calificación: cualificado",
  no_cualificado: "Calificación: no cualificado",
  warming: "Warming IA",
  humano: "Intervención humana",
  pause: "Pausado por humano",
  resume: "Seguimientos reanudados",
};

function fmtTs(ts: string | null | undefined): string {
  if (!ts) return "";
  const d = new Date(ts.includes("T") ? ts : ts.replace(" ", "T"));
  if (isNaN(d.getTime())) return ts;
  return d.toLocaleString("es-AR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export default function CrmPage() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [paused, setPaused] = useState(false);
  const [text, setText] = useState("");
  const [agentConnected, setAgentConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifs, setShowNotifs] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastMsgIdRef = useRef<string | null>(null);

  const loadLeads = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/crm/leads`, { credentials: "include" });
      if (res.status === 401) {
        router.replace("/login");
        return;
      }
      if (res.ok) setLeads(await res.json());
    } catch {
      /* backend abajo */
    }
  }, [router]);

  const loadDetail = useCallback(async (phone: string) => {
    try {
      const res = await fetch(`${API_URL}/crm/leads/${encodeURIComponent(phone)}`, { credentials: "include" });
      if (!res.ok) return;
      const data = await res.json();
      setMessages(data.messages || []);
      setEvents(data.events || []);
      setPaused(!!data.paused);
    } catch {
      /* ignore */
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/crm/notifications`, { credentials: "include" });
      if (res.ok) {
        const d = await res.json();
        setNotifications(d.notifications || []);
        setUnreadCount(d.unread || 0);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadLeads();
    loadNotifications();
    const checkAgent = () => {
      fetch(`${API_URL}/agent/state`)
        .then((r) => r.json())
        .then((d) => setAgentConnected(!!d.connected))
        .catch(() => setAgentConnected(false));
    };
    checkAgent();
    fetch(`${API_URL}/crm/status`, { credentials: "include" })
      .then((r) => r.json())
      .then((d) => setAgentConnected((prev) => prev || !!d.connected))
      .catch(() => {});
    const t = setInterval(() => {
      loadLeads();
      loadNotifications();
      checkAgent();
      if (selected) loadDetail(selected);
    }, 15000);
    return () => clearInterval(t);
  }, [loadLeads, loadDetail, loadNotifications, selected]);

  useEffect(() => {
    const last = messages[messages.length - 1]?.id;
    if (last && last !== lastMsgIdRef.current) {
      lastMsgIdRef.current = last;
      if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const send = async () => {
    if (!selected || !text.trim() || busy) return;
    const msg = text;
    setText("");
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/crm/leads/${encodeURIComponent(selected)}/send`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || "No se pudo enviar el mensaje");
      } else {
        setError(null);
        await loadDetail(selected);
        await loadLeads();
      }
    } catch {
      setError("No se pudo enviar el mensaje");
    } finally {
      setBusy(false);
    }
  };

  const togglePause = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_URL}/crm/leads/${encodeURIComponent(selected)}/${paused ? "resume" : "pause"}`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || "No se pudo cambiar el estado de pausa");
        return;
      }
      setError(null);
      setPaused(!paused);
      await loadDetail(selected);
      await loadLeads();
    } catch {
      setError("No se pudo cambiar el estado de pausa");
    } finally {
      setBusy(false);
    }
  };

  const bubbleClass = (m: Msg) => {
    if (m.direction === "in") return "self-start bg-white border border-gray-200 text-gray-800";
    if (m.actor === "humano") return "self-end bg-primary text-white border border-[#001F3D]";
    return "self-end bg-secondary text-primary";
  };

  return (
    <main className="relative z-10 mx-auto flex max-w-6xl flex-col gap-4 px-4 pt-32 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-primary">CRM Estudio VArq</h1>
          <p className="text-sm text-gray-500">Leads, conversaciones y control del bot</p>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/form-test" className="rounded border border-tertiary px-3 py-1.5 text-sm text-tertiary transition-all hover:bg-tertiary hover:text-white">
            Probar form
          </Link>
          {!agentConnected && (
            <Link href="/" className="rounded border border-[#ff7171] bg-[#ff7171] px-3 py-1.5 text-sm text-white transition-all hover:bg-primary">
              WhatsApp desconectado — conectar
            </Link>
          )}
          {agentConnected && (
            <span className="rounded bg-secondary px-3 py-1.5 text-sm font-semibold text-tertiary">
              WhatsApp conectado
            </span>
          )}
          <div className="relative">
            <button
              onClick={() => setShowNotifs(!showNotifs)}
              className="relative rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 transition-all hover:bg-gray-100"
            >
              🔔
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                  {unreadCount}
                </span>
              )}
            </button>
            {showNotifs && (
              <div className="absolute right-0 top-full z-50 mt-1 w-80 max-h-96 overflow-y-auto rounded-lg border bg-white shadow-lg">
                <div className="flex items-center justify-between border-b px-3 py-2">
                  <span className="text-sm font-semibold">Notificaciones</span>
                  {unreadCount > 0 && (
                    <button
                      onClick={async () => {
                        await fetch(`${API_URL}/crm/notifications/read-all`, { method: "POST", credentials: "include" });
                        loadNotifications();
                      }}
                      className="text-xs text-tertiary hover:underline"
                    >
                      Marcar todo leído
                    </button>
                  )}
                </div>
                {notifications.length === 0 && (
                  <p className="px-3 py-4 text-center text-sm text-gray-400">Sin notificaciones</p>
                )}
                {notifications.map((n) => (
                  <div
                    key={n.id}
                    onClick={async () => {
                      if (!n.read_at) {
                        await fetch(`${API_URL}/crm/notifications/read`, {
                          method: "POST",
                          credentials: "include",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ id: n.id }),
                        });
                        loadNotifications();
                      }
                      setSelected(n.phone);
                      setShowNotifs(false);
                    }}
                    className={`cursor-pointer border-b px-3 py-2 text-sm hover:bg-gray-50 ${!n.read_at ? "bg-blue-50 font-medium" : ""}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold">{n.titulo}</span>
                      <span className="text-[10px] text-gray-400">{fmtTs(n.created_at)}</span>
                    </div>
                    <p className="text-xs text-gray-600">{n.detalle}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          <button
            onClick={async () => {
              await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
              router.replace("/login");
            }}
            className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-600 transition-all hover:bg-gray-100"
          >
            Cerrar sesión
          </button>
        </div>
      </div>

      {error && <p className="rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      <div className="grid gap-4 overflow-hidden rounded-lg border border-gray-200 bg-white shadow md:grid-cols-[340px_1fr]">
        <aside className="max-h-[75vh] overflow-y-auto border-r border-gray-200">
          {leads.length === 0 && (
            <p className="p-4 text-sm text-gray-500">
              Aún no hay leads. Cuando llegue un mensaje por WhatsApp o un formulario, aparece acá.
            </p>
          )}
          {leads.map((l) => (
            <button
              key={l.phone}
              onClick={() => {
                setSelected(l.phone);
                loadDetail(l.phone);
              }}
              className={`flex w-full items-start justify-between gap-2 border-b border-gray-100 px-4 py-3 text-left transition-colors ${
                selected === l.phone ? "bg-primary text-white" : "hover:bg-secondary/60"
              }`}
            >
              <div className="min-w-0">
                <p className={`flex items-center gap-2 truncate font-semibold ${selected === l.phone ? "text-white" : "text-primary"}`}>
                  {l.name || l.phone}
                  {l.paused && (
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${selected === l.phone ? "bg-[#ff7171] text-white" : "bg-[#ff7171] text-white"}`}>
                      ⏸ Pausado
                    </span>
                  )}
                </p>
                <p className={`truncate text-xs ${selected === l.phone ? "text-blue-50" : "text-gray-500"}`}>
                  {l.last_message || "Sin mensajes"}
                </p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className={`rounded px-1.5 text-[10px] font-semibold uppercase ${selected === l.phone ? "bg-white/20 text-white" : "bg-secondary text-tertiary"}`}>
                  {l.stage}
                </span>
                {l.cualificado === "si" && (
                  <span className="rounded bg-green-100 px-1.5 text-[10px] font-bold text-green-700">
                    ✓ Cualificado
                  </span>
                )}
                {l.cualificado === "no" && l.razon_no_cual && (
                  <span className="rounded bg-red-50 px-1.5 text-[10px] text-red-600">
                    ✗ {l.razon_no_cual}
                  </span>
                )}
                {l.prox_seg_ts && (
                  <span className={`text-[10px] ${selected === l.phone ? "text-blue-100" : "text-gray-400"}`}>
                    seg: {fmtTs(l.prox_seg_ts)}
                  </span>
                )}
              </div>
            </button>
          ))}
        </aside>

        <section className="flex flex-col">
          {!selected ? (
            <div className="flex h-[50vh] items-center justify-center text-gray-400">
              Seleccioná un lead para ver la conversación
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 px-4 py-3">
                <div>
                  <p className="font-bold text-primary">{selected}</p>
                  <p className="text-xs text-gray-500">
                    Etapa: <span className="font-semibold text-tertiary">{leads.find((l) => l.phone === selected)?.stage || "—"}</span>
                    {paused && <span className="ml-2 rounded bg-[#ff7171] px-1.5 py-0.5 text-[10px] font-bold uppercase text-white">⏸ Pausado</span>}
                  </p>
                </div>
                <button
                  onClick={togglePause}
                  disabled={busy}
                  className={`rounded-md border px-4 py-1.5 text-sm font-semibold transition-all ${
                    paused
                      ? "border-tertiary text-tertiary hover:bg-tertiary hover:text-white"
                      : "border-[#ff7171] text-[#ff7171] hover:bg-[#ff7171] hover:text-white"
                  }`}
                >
                  {paused ? "▶ Reanudar seguimientos" : "⏸ Pausar bot"}
                </button>
              </div>

              {events.length > 0 && (
                <div className="border-b border-gray-200 bg-[#FAFAF4] px-4 py-3">
                  <p className="mb-2 text-xs font-bold uppercase tracking-wide text-tertiary">
                    Historial de instancias
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {events.slice(-12).map((e) => (
                      <span
                        key={e.id}
                        className={`rounded px-2 py-0.5 text-[11px] ${
                          e.actor === "humano" ? "bg-primary text-white" : "bg-white border border-gray-200 text-gray-600"
                        }`}
                        title={fmtTs(e.ts)}
                      >
                        {STEP_LABELS[e.step] || e.step}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex h-[40vh] flex-col gap-2 overflow-y-auto bg-gray-50 p-4">
                {messages.map((m) => (
                  <div key={m.id} className={`max-w-[75%] rounded-lg px-3 py-2 text-sm ${bubbleClass(m)}`}>
                    {m.text}
                    <span className="mt-1 block text-[10px] opacity-60">
                      {fmtTs(m.ts)} · {m.actor === "humano" ? "humano" : m.direction === "in" ? "cliente" : "bot"}
                    </span>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>

              <div className="mt-3 flex gap-2">
                <input
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Respondé como Estudio VArq (pausa el bot)..."
                  className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
                />
                <button
                  onClick={send}
                  disabled={busy}
                  className="rounded-md border border-[#001F3D] bg-primary px-5 py-2 text-sm font-semibold text-white transition-all hover:bg-tertiary"
                >
                  Enviar
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
