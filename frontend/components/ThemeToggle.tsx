"use client";
import { useEffect, useState } from "react";
import styles from "./ThemeToggle.module.css";

type Theme = "light" | "dark";

/**
 * Neumorphic sun/moon toggle. The actual theme decision is bootstrapped by
 * the inline script in layout.tsx (so the first paint is already correct);
 * this component reads what that set, exposes a toggle button, and persists
 * subsequent changes to localStorage.
 */
export function ThemeToggle() {
  // null while we wait for hydration — avoids rendering the wrong icon for a beat.
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const current: Theme =
      document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
    setTheme(current);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    if (next === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    try {
      localStorage.setItem("synapse-theme", next);
    } catch {
      /* ignore quota/private-mode errors — the in-memory state still works */
    }
  }

  // Reserve the space before hydration so the header layout doesn't jump.
  if (theme === null) {
    return <span className={styles.placeholder} aria-hidden />;
  }

  const label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";

  return (
    <button
      type="button"
      className={styles.toggle}
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      <span className={styles.iconWrap}>
        {theme === "dark" ? <Sun /> : <Moon />}
      </span>
    </button>
  );
}

function Moon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function Sun() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="4.2" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}
