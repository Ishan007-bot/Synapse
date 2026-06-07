"use client";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import type { GraphNode, SubgraphPayload } from "@/lib/types";
import styles from "./GraphPanel.module.css";

// react-force-graph-2d touches `window` on import, so we lazy-load it client-side.
const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

interface Props {
  payload: SubgraphPayload | null;
  emptyHint: string;
}

interface FGNode extends GraphNode { x?: number; y?: number; vx?: number; vy?: number; }
interface FGLink { source: string; target: string; predicate: string; }

const TYPE_COLOR: Record<string, string> = {
  Person: "#c44569",
  Organization: "#2c5f7c",
  Model: "#b85c00",
  Method: "#5d4e7b",
  Concept: "#6e6557",
  Place: "#4a7c59",
  Event: "#8b4513",
  Field: "#735b3e",
  Award: "#a07823",
};
const DEFAULT_COLOR = "#6e6557";

export function GraphPanel({ payload, emptyHint }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const fgRef = useRef<any>(null);
  const [size, setSize] = useState({ w: 600, h: 540 });
  const [selected, setSelected] = useState<FGNode | null>(null);

  // Responsive sizing — keep the graph filling its neumorphic well.
  useEffect(() => {
    if (!wrapRef.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ w: Math.round(width), h: Math.round(height) });
    });
    ro.observe(wrapRef.current);
    return () => ro.disconnect();
  }, []);

  // Convert the SubgraphPayload into the shape react-force-graph wants.
  const data = useMemo(() => {
    if (!payload) return { nodes: [] as FGNode[], links: [] as FGLink[] };
    return {
      nodes: payload.nodes.map((n) => ({ ...n })) as FGNode[],
      links: payload.edges.map((e) => ({
        source: e.source,
        target: e.target,
        predicate: e.predicate,
      })),
    };
  }, [payload]);

  // When new data arrives:
  //  1. Push the force config to spread nodes out — defaults are tuned for
  //     much smaller canvases, so on the full-width well they bunch up.
  //  2. Re-heat the simulation so it actually applies the new forces.
  //  3. Zoom-to-fit once it settles — reads as polish, and keeps everything
  //     visible regardless of how many seed entities we got.
  useEffect(() => {
    if (!fgRef.current || data.nodes.length === 0) return;
    const fg = fgRef.current;
    // Stronger node-node repulsion + longer links == roomier graph.
    fg.d3Force("charge").strength(-260);
    fg.d3Force("link").distance(75).strength(0.4);
    fg.d3ReheatSimulation();
    const t = setTimeout(() => fg.zoomToFit(500, 90), 700);
    return () => clearTimeout(t);
  }, [data]);

  if (!payload || payload.nodes.length === 0) {
    return (
      <div className={styles.well}>
        <div className={styles.emptyState}>
          <div className={styles.compass} aria-hidden>
            <span /><span /><span />
          </div>
          <p>{emptyHint}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.well} ref={wrapRef}>
      <ForceGraph2D
        ref={fgRef}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeRelSize={5}
        cooldownTicks={140}
        d3VelocityDecay={0.32}
        linkColor={() => "rgba(110, 101, 87, 0.35)"}
        linkWidth={(l: any) => (selected && (l.source.id === selected.id || l.target.id === selected.id) ? 2.2 : 0.8)}
        linkDirectionalParticles={(l: any) => (selected && (l.source.id === selected.id || l.target.id === selected.id) ? 3 : 0)}
        linkDirectionalParticleSpeed={0.006}
        linkDirectionalParticleColor={() => "#b85c00"}
        linkDirectionalParticleWidth={2}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, scale: number) => {
          // On the very first paint the d3 simulation hasn't assigned positions
          // yet, so node.x/y can be undefined/NaN. Skip this frame; the next
          // tick will draw with valid coordinates.
          if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

          const isSeed = !!node.is_seed;
          const isSel = selected?.id === node.id;
          const baseR = 4 + Math.sqrt(Math.max(1, node.degree)) * 1.4;
          const r = isSel ? baseR * 1.5 : isSeed ? baseR * 1.25 : baseR;
          const color = TYPE_COLOR[node.type] ?? DEFAULT_COLOR;

          // Soft glow halo for seed/selected nodes — sells the "this matters" feel.
          if (isSel || isSeed) {
            const haloR = r + (isSel ? 9 : 5);
            const grad = ctx.createRadialGradient(node.x, node.y, r, node.x, node.y, haloR);
            grad.addColorStop(0, isSel ? "rgba(184,92,0,0.55)" : "rgba(184,92,0,0.25)");
            grad.addColorStop(1, "rgba(184,92,0,0)");
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(node.x, node.y, haloR, 0, Math.PI * 2);
            ctx.fill();
          }

          // Node body
          ctx.beginPath();
          ctx.arc(node.x, node.y, r, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.lineWidth = isSeed || isSel ? 1.8 : 0;
          ctx.strokeStyle = "#efece4";
          if (isSeed || isSel) ctx.stroke();

          // Labels — only show for hubs to avoid visual noise, more when zoomed in.
          const showLabel = scale > 1.4 || isSel || isSeed || node.degree >= 5;
          if (showLabel) {
            const fontSize = Math.max(9, 11 / Math.sqrt(scale));
            ctx.font = `500 ${fontSize}px "Sora", sans-serif`;
            ctx.fillStyle = "#3a342c";
            ctx.textAlign = "center";
            ctx.textBaseline = "top";
            ctx.fillText(node.name, node.x, node.y + r + 4);
          }
        }}
        onNodeClick={(node: any) => setSelected(node as FGNode)}
        onBackgroundClick={() => setSelected(null)}
      />

      {selected && (
        <div className={styles.detail}>
          <div className={styles.detailHead}>
            <span
              className={styles.detailDot}
              style={{ background: TYPE_COLOR[selected.type] ?? DEFAULT_COLOR }}
              aria-hidden
            />
            <span className={styles.detailName}>{selected.name}</span>
            <span className={styles.detailType}>{selected.type}</span>
          </div>
          <div className={styles.detailMeta}>
            <span>degree {selected.degree}</span>
            {selected.is_seed && <span className={styles.detailSeed}>seed entity</span>}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className={styles.legend}>
        {Object.entries(TYPE_COLOR)
          .filter(([t]) => data.nodes.some((n) => n.type === t))
          .slice(0, 6)
          .map(([t, c]) => (
            <span key={t} className={styles.legendItem}>
              <span className={styles.legendDot} style={{ background: c }} />
              {t}
            </span>
          ))}
      </div>
    </div>
  );
}
