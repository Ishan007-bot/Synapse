"""Answer generation: turn retrieved context into a grounded, cited answer.

This is the "G" in RAG. The prompt forces the model to answer only from the
provided context and to cite source articles, so answers stay grounded and we
can later evaluate faithfulness (Phase 8).
"""
from __future__ import annotations

from typing import Iterable, Iterator

from .llm import LLMProvider, Message, get_provider
from .retrieval.vector_store import RetrievedChunk

SYSTEM_PROMPT = (
    "You are Synapse, a precise assistant answering questions about the field of "
    "artificial intelligence. Answer using ONLY the provided context. Cite the "
    "source article(s) you used in square brackets, e.g. [OpenAI]. If the context "
    "does not contain the answer, say you don't know — do not invent facts."
)


def build_context(chunks: Iterable[RetrievedChunk]) -> str:
    """Format retrieved chunks into a labelled context block for the prompt."""
    return "\n\n".join(f"[{c.source}] {c.text}" for c in chunks)


def _messages(query: str, chunks: Iterable[RetrievedChunk]) -> list[Message]:
    user = (
        f"Context:\n{build_context(chunks)}\n\n"
        f"Question: {query}\n\n"
        "Answer (with citations):"
    )
    return [Message("system", SYSTEM_PROMPT), Message("user", user)]


def generate_answer(
    query: str,
    chunks: list[RetrievedChunk],
    provider: LLMProvider | None = None,
) -> str:
    provider = provider or get_provider()
    return provider.generate(_messages(query, chunks), temperature=0.1)


def stream_answer(
    query: str,
    chunks: list[RetrievedChunk],
    provider: LLMProvider | None = None,
) -> Iterator[str]:
    provider = provider or get_provider()
    yield from provider.stream(_messages(query, chunks), temperature=0.1)
