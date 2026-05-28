"""Answer generation: turn retrieved context into a grounded, cited answer.

This is the "G" in RAG. The prompt forces the model to answer only from the
provided context and to cite source articles, so answers stay grounded and we
can later evaluate faithfulness (Phase 8).
"""
from __future__ import annotations

from typing import Iterable, Iterator

from .llm import LLMProvider, Message, get_provider
from .retrieval.graph_traversal import Triple
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


# ── Hybrid (Graph RAG) generation ──────────────────────────────────────────
# Same answering contract (cite sources, refuse if unsupported) but the prompt
# also exposes structured graph facts. Multi-hop questions get their bridge
# from the triples; the chunks ground the wording.

HYBRID_SYSTEM_PROMPT = (
    "You are Synapse, a precise assistant answering questions about the field "
    "of artificial intelligence. You are given two kinds of context:\n"
    "  (a) KNOWLEDGE GRAPH FACTS — short, structured statements extracted from "
    "the corpus.\n"
    "  (b) EXCERPTS — verbatim passages from the source articles.\n\n"
    "Rules:\n"
    "1. Answer using ONLY this context. If the context does not contain the "
    "answer, reply exactly: \"I don't know based on the provided context.\" "
    "Do not invent facts.\n"
    "2. For multi-hop questions, chain the relevant facts step by step before "
    "stating the final answer. Keep the chain brief (1-2 short sentences) and "
    "the final answer concise.\n"
    "3. Cite source article(s) in square brackets after the statements they "
    "support, e.g. \"[OpenAI]\" or \"[Anthropic, Andrew Ng]\". Only cite "
    "sources that actually appear in the EXCERPTS.\n"
    "4. Prefer the KNOWLEDGE GRAPH FACTS for connecting entities across "
    "articles, and the EXCERPTS for direct quotation and nuance."
)


def build_hybrid_context(chunks: Iterable[RetrievedChunk], triples: Iterable[Triple]) -> str:
    parts: list[str] = []
    triples = list(triples)
    if triples:
        parts.append("KNOWLEDGE GRAPH FACTS:")
        for t in triples:
            parts.append(f"- {t.to_sentence()}")
        parts.append("")
    parts.append("EXCERPTS:")
    for c in chunks:
        parts.append(f"[{c.source}] {c.text}")
    return "\n".join(parts)


def _hybrid_messages(
    query: str, chunks: Iterable[RetrievedChunk], triples: Iterable[Triple]
) -> list[Message]:
    user = (
        f"Context:\n{build_hybrid_context(chunks, triples)}\n\n"
        f"Question: {query}\n\n"
        "Answer (cite sources):"
    )
    return [Message("system", HYBRID_SYSTEM_PROMPT), Message("user", user)]


def generate_hybrid_answer(
    query: str,
    chunks: list[RetrievedChunk],
    triples: list[Triple],
    provider: LLMProvider | None = None,
) -> str:
    provider = provider or get_provider()
    return provider.generate(_hybrid_messages(query, chunks, triples), temperature=0.1)


def stream_hybrid_answer(
    query: str,
    chunks: list[RetrievedChunk],
    triples: list[Triple],
    provider: LLMProvider | None = None,
) -> Iterator[str]:
    """Yield Graph RAG answer text incrementally — what the FastAPI SSE endpoint will wrap."""
    provider = provider or get_provider()
    yield from provider.stream(_hybrid_messages(query, chunks, triples), temperature=0.1)
