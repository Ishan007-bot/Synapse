"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Stats } from "@/lib/types";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./Header.module.css";

const fmt = (n: number) => n.toLocaleString();

export function Header() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.stats()
      .then((s) => !cancelled && (setStats(s), setHealthy(true)))
      .catch(() => !cancelled && setHealthy(false));
    return () => { cancelled = true; };
  }, []);

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <div className={styles.mark} aria-hidden />
        <div className={styles.name}>
          <span className={styles.wordmark}>Synapse</span>
        </div>
      </div>

      <div className={styles.stats}>
        <Chip label="docs"      value={stats ? fmt(stats.documents) : "—"} />
        <Chip label="chunks"    value={stats ? fmt(stats.chunks) : "—"} />
        <Chip label="entities"  value={stats ? fmt(stats.entities) : "—"} />
        <Chip label="relations" value={stats ? fmt(stats.entity_relations) : "—"} />
        <span className={`${styles.status} ${healthy === true ? styles.statusOk : healthy === false ? styles.statusErr : ""}`}>
          {healthy === true ? "online" : healthy === false ? "api offline" : "…"}
        </span>
        <ThemeToggle />
      </div>
    </header>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.chip}>
      <span className={styles.chipValue}>{value}</span>
      <span className={styles.chipLabel}>{label}</span>
    </div>
  );
}
