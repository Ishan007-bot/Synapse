"use client";
import { useEffect, useRef } from "react";

/**
 * useScrollReveal — attaches an IntersectionObserver to a ref so the element
 * gains the `is-visible` class the first time it enters the viewport. Pair
 * with the `.reveal` class in globals.css and the optional --reveal-delay
 * custom property for a staggered cascade across siblings.
 *
 * Once revealed we stop observing — animations should fire once per page.
 */
export function useScrollReveal<T extends HTMLElement = HTMLDivElement>(
  options: IntersectionObserverInit = { threshold: 0.12, rootMargin: "0px 0px -60px 0px" },
) {
  const ref = useRef<T | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Bail out gracefully if the browser doesn't support IO.
    if (typeof IntersectionObserver === "undefined") {
      el.classList.add("is-visible");
      return;
    }
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          io.unobserve(entry.target);
        }
      }
    }, options);
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return ref;
}
