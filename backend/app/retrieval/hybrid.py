"""Hybrid retrieval: combine vector search with graph traversal.

For every query we gather three signals:

1. **Vector chunks** — the top-k chunks by cosine similarity (same as the
   naive-RAG baseline). This is the unconditional "text was relevant" signal.
2. **Seed entities** — entities the query mentions or is similar to. From
   those we run BFS to N hops and collect **triples** ``(source, predicate,
   target)`` — the structured layer the LLM can reason over.
3. **Entity-linked chunks** — additional chunks reachable from those entities
   via :MENTIONED_IN. This rescues chunks that don't look textually similar
   to the query but contain facts about the entities involved.

We dedupe chunks by id and respect a total chunk budget so the prompt stays
within the LLM's context window.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..db import Neo4jClient
from ..embeddings import Embedder
from .entity_linker import SeedEntity, link_entities
from .graph_traversal import Triple, chunks_for_entities, expand_subgraph
from .vector_store import RetrievedChunk, vector_search


@dataclass
class HybridContext:
    chunks: list[RetrievedChunk]
    triples: list[Triple]
    seed_entities: list[SeedEntity]
    visited_entity_ids: set[str] = field(default_factory=set)


def hybrid_retrieve(
    client: Neo4jClient,
    embedder: Embedder,
    query: str,
    *,
    k_chunks: int = 5,
    k_entity_chunks: int = 8,
    k_seed_entities: int = 5,
    hops: int = 2,
    max_triples: int = 60,
    max_chunks: int = 8,
) -> HybridContext:
    # 1. Plain vector retrieval over chunks.
    vector_chunks = vector_search(client, embedder, query, k=k_chunks)

    # 2. Find seed entities; if none, behave like naive RAG.
    seeds = link_entities(client, embedder, query, k_vector=k_seed_entities)

    triples: list[Triple] = []
    visited: set[str] = set()
    entity_chunks: list[RetrievedChunk] = []

    if seeds:
        visited, triples = expand_subgraph(
            client,
            [s.id for s in seeds],
            hops=hops,
            max_triples=max_triples,
        )

        # 3. Chunks that mention the visited entities, even if low textual similarity.
        rows = chunks_for_entities(
            client,
            list(visited),
            limit_per_entity=2,
            total_limit=k_entity_chunks,
        )
        # Convert to RetrievedChunk with score=0.0 (no vector score for these).
        entity_chunks = [
            RetrievedChunk(id=r["id"], text=r["text"], source=r["source"], score=0.0)
            for r in rows
        ]

    # 4. Merge chunks; vector hits keep their score, entity-linked chunks fill in
    #    the remaining budget. Dedupe by id.
    seen: set[str] = set()
    merged: list[RetrievedChunk] = []
    for c in vector_chunks + entity_chunks:
        if c.id in seen:
            continue
        seen.add(c.id)
        merged.append(c)
        if len(merged) >= max_chunks:
            break

    return HybridContext(
        chunks=merged,
        triples=triples,
        seed_entities=seeds,
        visited_entity_ids=visited,
    )
