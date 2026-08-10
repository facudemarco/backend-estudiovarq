"use client";

import Link from "next/link";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const FIELDS: { key: string; label: string; type?: string; placeholder?: string }[] = [
  { key: "name", label: "Nombre", placeholder: "Lead de prueba" },
  { key: "lastName", label: "Apellido", placeholder: "DummY" },
  { key: "phone", label: "Teléfono", placeholder: "5491100000000" },
  { key: "email", label: "Email", type: "email", placeholder: "test@dummy.com" },
  { key: "address", label: "Dirección", placeholder: "Calle Falsa 123" },
  { key: "zone", label: "Zona", placeholder: "CABA" },
  { key: "totalsM2", label: "Total m²", type: "number", placeholder: "35" },
  { key: "bathroom", label: "Baño", placeholder: "1" },
  { key: "kitchen", label: "Cocina", placeholder: "1" },
  { key: "livingRoom", label: "Living", placeholder: "1" },
  { key: "mainBedroom", label: "Dormitorio principal", placeholder: "1" },
  { key: "secondBedroom", label: "Dorm. secundario", placeholder: "0" },
  { key: "plants", label: "Plantas", placeholder: "1" },
  { key: "garage", label: "Cochera", placeholder: "0" },
  { key: "comments", label: "Comentarios", placeholder: "Lead generado por el form de prueba" },
];

export default function FormTestPage() {
  const [form, setForm] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/crm/test-form`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json().catch(() => ({}));
      setResult(res.ok ? `OK — lead creado: ${data.phone || "(sin phone)"}` : `ERROR — ${data.detail || res.status}`);
    } catch {
      setResult("ERROR — no se pudo conectar con el backend");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="relative z-10 mx-auto flex max-w-2xl flex-col gap-4 px-4 pt-32 pb-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary">Form de prueba (ficticio)</h1>
          <p className="text-sm text-gray-500">
            Inserta un lead directo en el CRM. No envía email ni toca n8n.
          </p>
        </div>
        <Link href="/crm" className="rounded border border-tertiary px-3 py-1.5 text-sm text-tertiary hover:bg-tertiary hover:text-white">
          ← Volver al CRM
        </Link>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow">
        <div className="grid gap-3 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <label key={f.key} className="flex flex-col gap-1 text-sm">
              <span className="font-semibold text-primary">{f.label}</span>
              <input
                type={f.type || "text"}
                value={form[f.key] || ""}
                placeholder={f.placeholder}
                onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                className="rounded border border-gray-300 px-3 py-2"
              />
            </label>
          ))}
        </div>
        <button
          onClick={submit}
          disabled={busy}
          className="mt-4 w-full rounded-md bg-primary px-5 py-2.5 font-semibold text-white transition-all hover:bg-tertiary disabled:opacity-50"
        >
          {busy ? "Enviando..." : "Enviar lead de prueba"}
        </button>
        {result && (
          <p className={`mt-3 rounded px-3 py-2 text-sm ${result.startsWith("OK") ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
            {result}
          </p>
        )}
      </div>
    </main>
  );
}