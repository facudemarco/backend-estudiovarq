"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || "http://localhost:3008";

export default function SofiaPage() {
  const router = useRouter();
  const [state, setState] = useState({ connected: false, hasAuth: false });
  const [qr, setQr] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;

    const checkState = async () => {
      try {
        const res = await fetch(`${AGENT_URL}/state`);
        const data = await res.json();
        if (!alive) return;
        setState(data);
        if (data.connected) {
          router.replace("/crm");
          return;
        }
        const qrRes = await fetch(`${AGENT_URL}/qr`);
        const qrData = await qrRes.json();
        if (alive) setQr(qrData.qr);
      } catch {
        if (alive) setError("El agente de WhatsApp no responde. Asegurate de que corra en el puerto 3008.");
      }
    };

    checkState();
    const t = setInterval(checkState, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [router]);

  return (
    <main className="flex min-h-[70vh] flex-col items-center justify-center px-4 pt-32 pb-16">
      <h1 className="mb-2 text-3xl font-bold text-primary">Sofía — Conexión de WhatsApp</h1>
      <p className="mb-8 max-w-md text-center text-sm text-gray-600">
        Escaneá el código QR con <strong>WhatsApp</strong> (Ajustes → Dispositivos vinculados →
        Vincular dispositivo) para conectar el número de Estudio VArq al agente.
      </p>

      {state.connected ? (
        <p className="text-lg text-green-700">¡Conectado! Redirigiendo al CRM...</p>
      ) : error ? (
        <div className="text-center">
          <p className="mb-3 text-red-600">{error}</p>
          <button
            className="rounded bg-primary px-4 py-2 text-white"
            onClick={() => {
              setError(null);
              window.location.reload();
            }}
          >
            Reintentar
          </button>
        </div>
      ) : qr ? (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={qr} alt="QR de WhatsApp" className="h-64 w-64" />
          <p className="mt-3 text-center text-xs text-gray-500">
            El QR se actualiza solo. Esperando escaneo...
          </p>
        </div>
      ) : (
        <p className="text-gray-500">Generando QR...</p>
      )}

      {state.hasAuth && !state.connected && (
        <button
          className="mt-6 text-sm text-red-600 underline"
          onClick={async () => {
            await fetch(`${AGENT_URL}/logout`, { method: "POST" });
            setQr(null);
          }}
        >
          Cerrar sesión actual y generar QR nuevo
        </button>
      )}
    </main>
  );
}
