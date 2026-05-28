import type { Metadata } from "next";
import { Fraunces, Sora, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Editorial serif display — distinctive variable axes (SOFT, WONK) give it character.
const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display",
  axes: ["SOFT", "WONK", "opsz"],
});

// Humanist sans for body — readable, modern, not Inter.
const sora = Sora({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body",
  weight: ["300", "400", "500", "600"],
});

// Mono for technical bits.
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Synapse — a graph that thinks across articles",
  description:
    "Graph RAG over a Wikipedia AI-field corpus. Ask multi-hop questions that span multiple articles; watch the knowledge graph light up as facts chain together.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fraunces.variable} ${sora.variable} ${jetbrains.variable}`}>
      <body>{children}</body>
    </html>
  );
}
