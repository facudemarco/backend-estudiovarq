"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        setError(d.detail || "Credenciales inválidas");
        return;
      }
      router.replace("/crm");
    } catch {
      setError("No se pudo conectar con el backend");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-[70vh] flex-col items-center justify-center px-4 pt-32 pb-16">
      <h1 className="mb-2 text-3xl font-bold text-primary">CRM Estudio VArq</h1>
      <p className="mb-8 max-w-md text-center text-sm text-gray-600">
        Iniciá sesión para acceder al panel de leads y conversaciones.
      </p>
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 shadow">
        <label className="mb-1 block text-sm font-semibold text-primary" htmlFor="username">
          Usuario
        </label>
        <input
          id="username"
          className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-tertiary focus:outline-none"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          required
        />
        <label className="mb-1 block text-sm font-semibold text-primary" htmlFor="password">
          Contraseña
        </label>
        <input
          id="password"
          type="password"
          className="mb-4 w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-tertiary focus:outline-none"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          required
        />
        {error && <p className="mb-3 rounded bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-tertiary disabled:opacity-60"
        >
          {busy ? "Ingresando..." : "Ingresar"}
        </button>
      </form>
      <Link href="/" className="mt-4 text-sm text-gray-500 underline hover:text-tertiary">
        ← Ver código QR de WhatsApp
      </Link>
    </main>
  );
}