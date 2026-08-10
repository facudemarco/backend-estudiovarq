import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CRM Estudio VArq",
  description: "Panel de leads, conversaciones y control del bot de WhatsApp",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-[#FAFAF4]">{children}</body>
    </html>
  );
}