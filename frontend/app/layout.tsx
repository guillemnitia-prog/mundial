import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ServiceWorker } from "@/components/ServiceWorker";

export const metadata: Metadata = {
  title: "WorldCup Betting Analyzer",
  description: "Análisis de value betting para el Mundial 2026 — grupo privado.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Mundial" },
};

export const viewport: Viewport = {
  themeColor: "#0A1712",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <ServiceWorker />
        {children}
      </body>
    </html>
  );
}
