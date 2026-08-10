"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "https://estudiovarq.com.ar/agent";

type Lead = {
  phone: string;
  name: string;
  stage: string;
  etapa_seg: string;
  prox_seg_ts: string;
  last_message: string;
  paused: boolean;
};

type Msg = { id: string; direction: string; text: string; ts: string; actor?: string };
type Event = { id: string; step: string; ts: string; actor?: string };

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
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [paused, setPaused] = useState(false);
  const [text, setText] = useState("");
  const [agentConnected, setAgentConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const lastMsgIdRef = useRef<string | null>(null);

  const loadLeads = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/crm/leads`);
      if (res.ok) setLeads(await res.json());
    } catch {
      /* backend abajo */
    }
  }, []);

  const loadDetail = useCallback(async (phone: string) => {
    try {
      const res = await fetch(`${API_URL}/crm/leads/${encodeURIComponent(phone)}`);
      if (!res.ok) return;
      const data = await res.json();
      setMessages(data.messages || []);
      setEvents(data.events || []);
      setPaused(!!data.paused);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    loadLeads();
    const checkAgent = () => {
      fetch(`${AGENT_URL}/state`)
        .then((r) => r.json())
        .then((d) => setAgentConnected(!!d.connected))
        .catch(() => setAgentConnected(false));
    };
    checkAgent();
    fetch(`${API_URL}/crm/status`)
      .then((r) => r.json())
      .then((d) => setAgentConnected((prev) => prev || !!d.connected))
      .catch(() => {});
    const t = setInterval(() => {
      loadLeads();
      checkAgent();
      if (selected) loadDetail(selected);
    }, 5000);
    return () => clearInterval(t);
  }, [loadLeads, loadDetail, selected]);

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
