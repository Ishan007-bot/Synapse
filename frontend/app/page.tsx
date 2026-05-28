"use client";
import { useRef, useState } from "react";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { AnswerPanel } from "@/components/AnswerPanel";
import { GraphPanel } from "@/components/GraphPanel";
import { ModeToggle, type Mode } from "@/components/ModeToggle";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import { api } from "@/lib/api";
import { streamQuery } from "@/lib/sse";
import type { SourceInfo, SubgraphPayload } from "@/lib/types";
import styles from "./page.module.css";

export default function Home() {
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<Mode>("graph");

  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [subgraph, setSubgraph] = useState<SubgraphPayload | null>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasAsked, setHasAsked] = useState(false);

  const abortRef = useRef<AbortController | null>(null);

  const reveal1 = useScrollReveal<HTMLDivElement>();
  const reveal2 = useScrollReveal<HTMLDivElement>();

  function reset() {
    setAnswer("");
    setSources([]);
    setSubgraph(null);
    setError(null);
  }

  async function ask() {
    const q = question.trim();
    if (!q) return;
    // Cancel any in-flight stream before starting a new one.
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    reset();
    setHasAsked(true);
    setIsStreaming(true);

    try {
      if (mode === "graph") {
        await streamQuery(
          q,
          {
            onContext: (ctx) => {
              setSources(ctx.sources);
              setSubgraph(ctx.subgraph);
            },
            onToken: (text) => setAnswer((a) => a + text),
            onDone: (full) => {
              setAnswer(full.answer);
              setSources(full.sources);
              setSubgraph(full.subgraph);
            },
            onError: (msg) => setError(msg),
          },
          { hops: 2, signal: ctrl.signal },
        );
      } else {
        const res = await api.queryNaive(q, 5);
        setAnswer(res.answer);
        setSources(res.sources);
        // No graph in naive mode — keep panel empty so the contrast is visible.
        setSubgraph(null);
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
    } finally {
      setIsStreaming(false);
    }
  }

  const emptyAnswer = !hasAsked && !error;

  return (
    <>
      <Header />
      <main className={styles.main}>
        <Hero
          value={question}
          onChange={setQuestion}
          onSubmit={ask}
          loading={isStreaming}
        />

        <section ref={reveal1} className={`${styles.modeRow} reveal`}>
          <ModeToggle mode={mode} onChange={setMode} disabled={isStreaming} />
          <p className={styles.modeHint}>
            {mode === "graph"
              ? "Hybrid: vector chunks + graph traversal. The same query that fails on the right…"
              : "Vector-only RAG. Toggle to Graph RAG to compare on multi-hop questions."}
          </p>
        </section>

        <section ref={reveal2} className={`${styles.results} reveal`} style={{ ["--reveal-delay" as string]: "100ms" }}>
          <div className={styles.answerCol}>
            <AnswerPanel
              answer={answer}
              sources={sources}
              isStreaming={isStreaming}
              error={error}
              empty={emptyAnswer}
            />
          </div>
          <div className={styles.graphCol}>
            <GraphPanel
              payload={subgraph}
              emptyHint={
                mode === "naive"
                  ? "Naive RAG doesn't traverse a graph — switch to Graph RAG and ask a question to light it up."
                  : "Ask a question and the subgraph the system used to answer it will appear here, with seed entities glowing in amber."
              }
            />
          </div>
        </section>

        <footer className={styles.footer}>
          <span>built with neo4j · sentence-transformers · groq · fastapi · next.js</span>
        </footer>
      </main>
    </>
  );
}
