"use client";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import styles from "./Hero.module.css";

const SAMPLE_QUESTIONS: string[] = [
  "Name AI models created by people who previously worked at OpenAI.",
  "Who founded Anthropic and where did they come from?",
  "Which lab is Demis Hassabis associated with?",
  "Who advised Yoshua Bengio?",
];

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function Hero({ value, onChange, onSubmit, loading }: Props) {
  const headlineRef = useScrollReveal<HTMLDivElement>();
  const inputRef = useScrollReveal<HTMLDivElement>();
  const chipsRef = useScrollReveal<HTMLDivElement>();

  return (
    <section className={styles.hero}>
      <div ref={headlineRef} className={`${styles.head} reveal`}>
        <p className={styles.eyebrow}>Knowledge graph · Retrieval-augmented generation</p>
        <h1 className={styles.title}>
          A graph that <em className={styles.italic}>thinks</em>
          <br />
          across articles.
        </h1>
        <p className={styles.lede}>
          Ask a question that crosses multiple Wikipedia entries about the AI field.
          Synapse chains facts through a knowledge graph it built from the corpus —
          retrieval that goes where vector similarity alone can&rsquo;t.
        </p>
      </div>

      <div
        ref={inputRef}
        className={`${styles.inputWrap} reveal`}
        style={{ ["--reveal-delay" as string]: "120ms" }}
      >
        <form
          className={styles.inputForm}
          onSubmit={(e) => { e.preventDefault(); if (!loading && value.trim()) onSubmit(); }}
        >
          <input
            className={styles.input}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Ask anything about the AI field…"
            spellCheck={false}
            autoFocus
            disabled={loading}
          />
          <button
            type="submit"
            className={styles.submit}
            disabled={loading || !value.trim()}
            aria-label="Ask"
          >
            <span className={styles.submitInner}>
              {loading ? <Spinner /> : <Arrow />}
            </span>
          </button>
        </form>
      </div>

      <div
        ref={chipsRef}
        className={`${styles.chips} reveal`}
        style={{ ["--reveal-delay" as string]: "260ms" }}
      >
        <span className={styles.tryLabel}>try</span>
        {SAMPLE_QUESTIONS.map((q, i) => (
          <button
            key={q}
            type="button"
            className={styles.chip}
            style={{ animationDelay: `${i * 60}ms` }}
            onClick={() => { onChange(q); }}
            disabled={loading}
          >
            {q}
          </button>
        ))}
      </div>
    </section>
  );
}

function Arrow() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function Spinner() {
  return (
    <svg className={styles.spin} width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden>
      <path d="M21 12a9 9 0 1 1-6.2-8.55" />
    </svg>
  );
}
