"""Graph RAG — hybrid retrieval (vectors + knowledge graph) + grounded generation.

This is the system Phase 8 will measure against the naive baseline (`app/rag.py`).
The flow is:

    query
       ├── vector search over chunks         ──┐
       └── entity linking ──► subgraph BFS ──┐ ├── hybrid context ──► LLM ──► answer
                                  └─► linked chunks ─┘                          │
                                                                                ▼
                                                                          cited sources

Query it (Neo4j up, indexes built, graph built, LLM key in .env):
    cd backend
    python -m app.graph_rag "Who founded Anthropic and where did they come from?"
    python -m app.graph_rag                                # interactive prompt
    python -m app.graph_rag --retrieve-only "..."          # show context only, no LLM
    python -m app.graph_rag --compare "..."                # naive vs Graph RAG side-by-side
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from .console import enable_utf8
from .db import Neo4jClient
from .embeddings import Embedder
from .generation import generate_answer, generate_hybrid_answer
from .retrieval.entity_linker import SeedEntity
from .retrieval.graph_traversal import Triple
from .retrieval.hybrid import HybridContext, hybrid_retrieve
from .retrieval.vector_store import RetrievedChunk, vector_search


@dataclass
class GraphRAGResult:
    answer: str
    context: HybridContext


class GraphRAG:
    """Hybrid retrieval + generation. Reusable across queries."""

    def __init__(self) -> None:
        self.embedder = Embedder()
        self.client = Neo4jClient()

    def retrieve(self, question: str, **kw) -> HybridContext:
        return hybrid_retrieve(self.client, self.embedder, question, **kw)

    def answer(self, question: str, **kw) -> GraphRAGResult:
        context = self.retrieve(question, **kw)
        ans = generate_hybrid_answer(question, context.chunks, context.triples)
        return GraphRAGResult(answer=ans, context=context)

    # Helpers for the side-by-side comparison mode below.
    def naive_answer(self, question: str, k: int = 5) -> tuple[str, list[RetrievedChunk]]:
        chunks = vector_search(self.client, self.embedder, question, k=k)
        return generate_answer(question, chunks), chunks

    def close(self) -> None:
        self.client.close()


# ── CLI ───────────────────────────────────────────────────────────────────


def _print_seeds(seeds: list[SeedEntity]) -> None:
    if not seeds:
        print("  (no seed entities linked)")
        return
    for s in seeds[:8]:
        print(f"  - {s.name:35} [{s.type}]  via={s.via}  score={s.score:.3f}")


def _print_triples(triples: list[Triple], n: int = 15) -> None:
    if not triples:
        print("  (no graph triples)")
        return
    for t in triples[:n]:
        print(f"  - {t.to_sentence()}")
    if len(triples) > n:
        print(f"  ... +{len(triples) - n} more triples")


def _print_chunks_preview(chunks: list[RetrievedChunk], n: int = 5) -> None:
    for c in chunks[:n]:
        marker = f"score {c.score:.3f}" if c.score > 0 else "via-entity"
        print(f"  [{c.source}] ({marker})  {c.text[:120]}...")


def _print_sources(chunks: list[RetrievedChunk]) -> None:
    seen: set[str] = set()
    print("\nsources:")
    for c in chunks:
        if c.source in seen:
            continue
        seen.add(c.source)
        marker = f"score {c.score:.3f}" if c.score > 0 else "via-entity"
        print(f"  - {c.source}  ({marker})")


def main() -> None:
    enable_utf8()
    parser = argparse.ArgumentParser(description="Query the Graph RAG system.")
    parser.add_argument("question", nargs="?", help="question to ask")
    parser.add_argument("--retrieve-only", action="store_true", help="show context only, skip LLM")
    parser.add_argument("--compare", action="store_true", help="naive RAG vs Graph RAG side by side")
    parser.add_argument("--hops", type=int, default=2, help="graph traversal depth")
    args = parser.parse_args()

    rag = GraphRAG()
    try:
        questions = [args.question] if args.question else None
        while True:
            question = questions.pop(0) if questions else input("\nquestion> ").strip()
            if not question:
                break

            context = rag.retrieve(question, hops=args.hops)

            print(f"\n=== {question} ===")
            print("\nseed entities:")
            _print_seeds(context.seed_entities)
            print(f"\ngraph triples ({len(context.triples)}):")
            _print_triples(context.triples)
            print(f"\ncontext chunks ({len(context.chunks)}):")
            _print_chunks_preview(context.chunks)

            if args.retrieve_only:
                pass
            elif args.compare:
                graph_ans = generate_hybrid_answer(question, context.chunks, context.triples)
                print("\n--- Naive RAG ---")
                naive_ans, naive_chunks = rag.naive_answer(question)
                print(naive_ans)
                _print_sources(naive_chunks)
                print("\n--- Graph RAG ---")
                print(graph_ans)
                _print_sources(context.chunks)
            else:
                ans = generate_hybrid_answer(question, context.chunks, context.triples)
                print(f"\n{ans}")
                _print_sources(context.chunks)

            if questions is not None and not questions:
                break
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        rag.close()


if __name__ == "__main__":
    main()
