"use client";
import { useEffect, useRef } from "react";
import type { SourceInfo } from "@/lib/types";
import styles from "./AnswerPanel.module.css";

interface Props {
  answer: string;
  sources: SourceInfo[];
  isStreaming: boolean;
  error: string | null;
  empty: boolean;
}

export function AnswerPanel({ answer, sources, isStreaming, error, empty }: Props) {
  const scrollerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom while tokens arrive so the new text stays in view.
  useEffect(() => {
    if (!isStreaming || !scrollerRef.current) return;
    scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
  }, [answer, isStreaming]);

  return (
    <article className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>Answer</h3>
        {isStreaming && (
          <span className={styles.streamingTag}>
            <span className={styles.streamDot} aria-hidden />
            streaming
          </span>
        )}
      </div>

      <div className={styles.body} ref={scrollerRef}>
        {empty ? (
          <p className={styles.placeholder}>
            Your answer will appear here, with citations linking to the source articles
            and a knowledge-graph trace on the right.
          </p>
        ) : error ? (
          <div className={styles.error}>
            <strong>Couldn&rsquo;t answer:</strong> {error}
          </div>
        ) : (
          <p className={styles.text}>
            {renderWithCitations(answer)}
            {isStreaming && <span className={styles.caret} aria-hidden />}
          </p>
        )}
      </div>

      {sources.length > 0 && (
        <div className={styles.sources}>
          <span className={styles.sourcesLabel}>Sources</span>
          <div className={styles.sourceList}>
            {sources.map((s) => (
              <span
                key={`${s.name}-${s.via}`}
                className={`${styles.source} ${s.via === "entity" ? styles.viaEntity : styles.viaVector}`}
                title={s.via === "vector" ? `vector score ${s.score.toFixed(3)}` : "linked via entity in the graph"}
              >
                <span className={styles.sourceBullet} aria-hidden />
                <span className={styles.sourceName}>{s.name}</span>
                <span className={styles.sourceMeta}>
                  {s.via === "vector" ? s.score.toFixed(2) : "↪ graph"}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}

/** Wrap citation tokens like [OpenAI, Anthropic] in a styled span without rebuilding the text. */
function renderWithCitations(text: string): React.ReactNode {
  if (!text) return null;
  const parts: React.ReactNode[] = [];
  const re = /\[([^\]]+)\]/g;
  let lastIdx = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > lastIdx) parts.push(text.slice(lastIdx, match.index));
    parts.push(
      <span key={`c-${key++}`} className={styles.citation}>
        {match[1]}
      </span>,
    );
    lastIdx = match.index + match[0].length;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts;
}
