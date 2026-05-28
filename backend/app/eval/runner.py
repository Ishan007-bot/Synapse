"""Run the eval: Naive RAG vs Graph RAG, scored on the same questions.

CLI (Neo4j up, indexes built, LLM key in .env — uses Groq by default for both
the answering models and the judge):
    cd backend
    python -m app.eval.runner                       # all questions, both systems
    python -m app.eval.runner --ids mh01,mh02        # just these questions
    python -m app.eval.runner --no-cache             # ignore disk cache
    python -m app.eval.runner --report-path data/eval/report.md

Outputs:
  data/eval/results.json   — full per-question metric data
  data/eval/report.md      — human-readable comparison table

Both files are gitignored; commit a hand-picked snapshot if you want the
numbers in the repo.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from ..console import enable_utf8
from ..embeddings import Embedder
from ..graph_rag import GraphRAG
from ..llm import get_provider
from ..retrieval.graph_traversal import Triple
from ..retrieval.vector_store import RetrievedChunk
from .dataset import EVAL_SET, EvalQuestion
from .judge import Judge
from .metrics import compute_metrics

logger = logging.getLogger(__name__)

_OUT_DIR = Path(__file__).resolve().parents[3] / "data" / "eval"


@dataclass
class SystemRun:
    """One (question, system) row of the comparison."""
    question_id: str
    system: str  # "naive" | "graph"
    answer: str
    contexts: list[str]
    metrics: dict[str, float]


def _chunks_as_contexts(chunks: list[RetrievedChunk]) -> list[str]:
    return [f"[{c.source}] {c.text}" for c in chunks]


def _triples_as_contexts(triples: list[Triple]) -> list[str]:
    # Each triple becomes a one-sentence "context" item. Judges see them as
    # peers of the chunk excerpts; whichever helped the answer counts.
    return [t.to_sentence() for t in triples]


def _format_row(label: str, m: dict[str, float]) -> str:
    return (
        f"  {label:7}  faith {m['faithfulness']:.2f}   "
        f"relev {m['answer_relevancy']:.2f}   "
        f"prec {m['context_precision']:.2f}   "
        f"recall {m['context_recall']:.2f}"
    )


def _aggregate(runs: list[SystemRun], system: str, type_filter: str | None = None) -> dict[str, float]:
    selected = [
        r for r in runs
        if r.system == system
        and (type_filter is None or _question_type(r.question_id) == type_filter)
    ]
    if not selected:
        return {k: 0.0 for k in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")}
    keys = selected[0].metrics.keys()
    return {k: sum(r.metrics[k] for r in selected) / len(selected) for k in keys}


def _question_type(qid: str) -> str:
    return next((q.type for q in EVAL_SET if q.id == qid), "")


def _write_markdown_report(path: Path, runs: list[SystemRun]) -> None:
    lines: list[str] = []
    lines.append("# Synapse — Graph RAG vs Naive RAG evaluation\n")
    lines.append("RAGAS-style metrics (faithfulness, answer relevancy, context precision, "
                 "context recall), scored 0–1 (higher = better).\n")

    # ── Aggregate table ──
    lines.append("## Aggregate scores\n")
    lines.append("| Split | System | Faithfulness | Answer Relevancy | Context Precision | Context Recall |")
    lines.append("|-------|--------|--------------|------------------|-------------------|----------------|")
    for tf, label in [(None, "Overall"), ("multi-hop", "Multi-hop only"), ("single-hop", "Single-hop only")]:
        for system in ("naive", "graph"):
            agg = _aggregate(runs, system, type_filter=tf)
            lines.append(
                f"| {label} | **{'Graph RAG' if system == 'graph' else 'Naive RAG'}** "
                f"| {agg['faithfulness']:.2f} "
                f"| {agg['answer_relevancy']:.2f} "
                f"| {agg['context_precision']:.2f} "
                f"| {agg['context_recall']:.2f} |"
            )
    lines.append("")

    # ── Per-question detail ──
    lines.append("## Per-question detail\n")
    by_question: dict[str, dict[str, SystemRun]] = {}
    for r in runs:
        by_question.setdefault(r.question_id, {})[r.system] = r
    for q in EVAL_SET:
        rs = by_question.get(q.id, {})
        if not rs:
            continue
        lines.append(f"### `{q.id}` ({q.type}) — {q.question}\n")
        lines.append(f"_Reference:_ {q.reference}\n")
        for system in ("naive", "graph"):
            r = rs.get(system)
            if r is None:
                continue
            m = r.metrics
            sys_label = "Graph RAG" if system == "graph" else "Naive RAG"
            lines.append(f"**{sys_label}** — faith `{m['faithfulness']:.2f}`, "
                         f"relev `{m['answer_relevancy']:.2f}`, "
                         f"prec `{m['context_precision']:.2f}`, "
                         f"recall `{m['context_recall']:.2f}`")
            lines.append("")
            lines.append("> " + r.answer.replace("\n", "\n> "))
            lines.append("")
        lines.append("---\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    enable_utf8()
    parser = argparse.ArgumentParser(description="Eval Naive RAG vs Graph RAG with RAGAS-style metrics.")
    parser.add_argument("--ids", default=None, help="comma-separated question ids to include")
    parser.add_argument("--systems", default="naive,graph", help="systems to run (comma-separated)")
    parser.add_argument("--no-cache", action="store_true", help="bypass the judge cache for this run")
    parser.add_argument("--report-path", default=str(_OUT_DIR / "report.md"))
    parser.add_argument("--results-path", default=str(_OUT_DIR / "results.json"))
    args = parser.parse_args()

    ids = set(args.ids.split(",")) if args.ids else None
    systems = [s.strip() for s in args.systems.split(",")]
    questions = [q for q in EVAL_SET if ids is None or q.id in ids]

    if args.no_cache:
        # The cache lives in data/eval/judge_cache; the simplest "no cache" is to
        # rename it for this run. We just clear here for clarity.
        cache_dir = _OUT_DIR / "judge_cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink()
            print(f"[no-cache] cleared {cache_dir}")

    print(f"=== Synapse eval — {len(questions)} questions, systems={systems} ===\n")

    rag = GraphRAG()
    judge = Judge(provider=get_provider())
    embedder = rag.embedder  # share the loaded embedder
    runs: list[SystemRun] = []
    t0 = time.time()

    try:
        for i, q in enumerate(questions, start=1):
            print(f"[{i}/{len(questions)}] {q.id} ({q.type}): {q.question}")

            if "naive" in systems:
                naive_text, naive_chunks = rag.naive_answer(q.question, k=5)
                naive_contexts = _chunks_as_contexts(naive_chunks)
                naive_metrics = compute_metrics(
                    judge, embedder,
                    question=q.question,
                    answer=naive_text,
                    reference=q.reference,
                    contexts=naive_contexts,
                )
                runs.append(SystemRun(
                    question_id=q.id, system="naive",
                    answer=naive_text, contexts=naive_contexts,
                    metrics=asdict(naive_metrics),
                ))
                print(_format_row("naive", asdict(naive_metrics)))

            if "graph" in systems:
                graph_result = rag.answer(q.question, hops=2, k_chunks=5)
                # rebuild contexts: chunks + graph triples
                ctx = rag.retrieve(q.question, hops=2, k_chunks=5)
                graph_contexts = _chunks_as_contexts(ctx.chunks) + _triples_as_contexts(ctx.triples)
                graph_metrics = compute_metrics(
                    judge, embedder,
                    question=q.question,
                    answer=graph_result.answer,
                    reference=q.reference,
                    contexts=graph_contexts,
                )
                runs.append(SystemRun(
                    question_id=q.id, system="graph",
                    answer=graph_result.answer, contexts=graph_contexts,
                    metrics=asdict(graph_metrics),
                ))
                print(_format_row("graph", asdict(graph_metrics)))
            print()
    finally:
        rag.close()

    # ── Outputs ──
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path(args.results_path).write_text(
        json.dumps([asdict(r) for r in runs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_markdown_report(Path(args.report_path), runs)

    print("=" * 64)
    print("AGGREGATE — averaged across all evaluated questions:")
    print()
    for tf, label in [(None, "Overall"), ("multi-hop", "Multi-hop"), ("single-hop", "Single-hop")]:
        print(f"  {label}:")
        for system in systems:
            agg = _aggregate(runs, system, type_filter=tf)
            print(_format_row(system, agg))
        print()
    print(f"  elapsed: {time.time() - t0:.1f}s")
    print(f"  json:    {args.results_path}")
    print(f"  report:  {args.report_path}")


if __name__ == "__main__":
    main()
