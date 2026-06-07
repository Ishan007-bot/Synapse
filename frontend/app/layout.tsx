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

// This runs BEFORE React hydrates so the first paint is already in the user's
// chosen theme — no light/dark flash on dark-mode users' reload.
const themeInit = `
(function(){
  try {
    var saved = localStorage.getItem('synapse-theme');
    var preferDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    if (saved === 'dark' || (!saved && preferDark)) {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch (e) {}
})();
`.trim();

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${fraunces.variable} ${sora.variable} ${jetbrains.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
