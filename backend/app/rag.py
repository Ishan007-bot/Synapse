"""Naive (vector-only) RAG — the baseline Graph RAG will be measured against.

Pipeline: embed query -> vector top-k -> grounded LLM answer with citations.

Query it (Neo4j up, index built, LLM key in .env):
    cd backend
    python -m app.rag "Who founded OpenAI?"
    python -m app.rag                       # interactive prompt
    python -m app.rag --retrieve-only "..." # show chunks only, no LLM (no key needed)
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass

from .config import settings
from .console import enable_utf8
from .db import Neo4jClient
from .embeddings import Embedder
from .generation import generate_answer
from .retrieval.vector_store import RetrievedChunk, vector_search


@dataclass
class RAGResult:
    answer: str
    chunks: list[RetrievedChunk]


class NaiveRAG:
    """Vector-only retrieval + generation. Reusable; holds the heavy objects."""

    def __init__(self) -> None:
        self.embedder = Embedder()
        self.client = Neo4jClient()

    def retrieve(self, question: str, k: int | None = None) -> list[RetrievedChunk]:
        return vector_search(self.client, self.embedder, question, k or settings.top_k)

    def answer(self, question: str, k: int | None = None) -> RAGResult:
        chunks = self.retrieve(question, k)
        answer = generate_answer(question, chunks)
        return RAGResult(answer=answer, chunks=chunks)

    def close(self) -> None:
        self.client.close()


def _print_sources(chunks: list[RetrievedChunk]) -> None:
    print("\nsources:")
    seen: set[str] = set()
    for c in chunks:
        tag = f"  - {c.source}  (score {c.score:.3f})"
        if c.source not in seen:
            print(tag)
            seen.add(c.source)


def main() -> None:
    enable_utf8()
    parser = argparse.ArgumentParser(description="Query the naive RAG baseline.")
    parser.add_argument("question", nargs="?", help="question to ask")
    parser.add_argument("-k", type=int, default=settings.top_k, help="number of chunks to retrieve")
    parser.add_argument(
        "--retrieve-only",
        action="store_true",
        help="show retrieved chunks without calling the LLM (no API key needed)",
    )
    args = parser.parse_args()

    rag = NaiveRAG()
    try:
        questions = [args.question] if args.question else None
        while True:
            question = questions.pop(0) if questions else input("\nquestion> ").strip()
            if not question:
                break
            if args.retrieve_only:
                for c in rag.retrieve(question, args.k):
                    print(f"\n[{c.source}] (score {c.score:.3f})\n{c.text[:300]}...")
            else:
                result = rag.answer(question, args.k)
                print(f"\n{result.answer}")
                _print_sources(result.chunks)
            if questions is not None and not questions:
                break
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        rag.close()


if __name__ == "__main__":
    main()
