"use client";
import styles from "./ModeToggle.module.css";

export type Mode = "graph" | "naive";

interface Props {
  mode: Mode;
  onChange: (m: Mode) => void;
  disabled?: boolean;
}

/**
 * A neumorphic segmented control: the active mode gets a pressed (inset)
 * shadow while the inactive option stays flush with the surface.
 */
export function ModeToggle({ mode, onChange, disabled }: Props) {
  return (
    <div className={styles.toggle} role="tablist" aria-label="retrieval mode">
      <button
        type="button"
        role="tab"
        aria-selected={mode === "graph"}
        className={`${styles.option} ${mode === "graph" ? styles.active : ""}`}
        onClick={() => onChange("graph")}
        disabled={disabled}
      >
        Graph RAG
        <span className={styles.dot} aria-hidden />
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === "naive"}
        className={`${styles.option} ${mode === "naive" ? styles.active : ""}`}
        onClick={() => onChange("naive")}
        disabled={disabled}
      >
        Naive (baseline)
      </button>
    </div>
  );
}
