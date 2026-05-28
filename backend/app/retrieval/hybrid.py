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
from ..schemas import (
    ChunkInfo,
    GraphEdge,
    GraphNode,
    RAGAnswer,
    SourceInfo,
    SubgraphPayload,
)
from .entity_linker import SeedEntity, link_entities
from .graph_traversal import EntityInfo, Triple, chunks_for_entities, expand_subgraph
from .vector_store import RetrievedChunk, vector_search


@dataclass
class HybridContext:
    chunks: list[RetrievedChunk]
    triples: list[Triple]
    seed_entities: list[SeedEntity]
    visited_entity_ids: set[str] = field(default_factory=set)
    entity_info: dict[str, EntityInfo] = field(default_factory=dict)

    # ── payload assembly (consumed by the API + frontend) ────────────────

    def subgraph_payload(self) -> SubgraphPayload:
        """Convert triples + entity info into a viz-ready node/edge graph."""
        seed_ids = {s.id for s in self.seed_entities}
        degree: dict[str, int] = {}
        edges: list[GraphEdge] = []
        used_ids: set[str] = set()

        for t in self.triples:
            edges.append(GraphEdge(source=t.source_id, target=t.target_id, predicate=t.predicate))
            for nid in (t.source_id, t.target_id):
                degree[nid] = degree.get(nid, 0) + 1
                used_ids.add(nid)

        # Make sure seed entities show up even if they had no edges in the subgraph.
        for s in self.seed_entities:
            used_ids.add(s.id)
            self.entity_info.setdefault(s.id, EntityInfo(s.id, s.name, s.type))

        nodes = [
            GraphNode(
                id=info.id,
                name=info.name,
                type=info.type or "Concept",
                is_seed=info.id in seed_ids,
                degree=degree.get(info.id, 0),
            )
            for nid, info in self.entity_info.items()
            if nid in used_ids
        ]
        return SubgraphPayload(nodes=nodes, edges=edges, seed_ids=sorted(seed_ids))

    def source_list(self) -> list[SourceInfo]:
        """Unique source articles in the order they first appear."""
        seen: set[str] = set()
        sources: list[SourceInfo] = []
        for c in self.chunks:
            if c.source in seen:
                continue
            seen.add(c.source)
            via = "vector" if c.score > 0 else "entity"
            sources.append(SourceInfo(name=c.source, score=c.score, via=via))
        return sources

    def to_answer(self, answer_text: str) -> RAGAnswer:
        """Assemble the full Pydantic response for the API/frontend."""
        return RAGAnswer(
            answer=answer_text,
            sources=self.source_list(),
            chunks=[
                ChunkInfo(id=c.id, source=c.source, text=c.text, score=c.score)
                for c in self.chunks
            ],
            subgraph=self.subgraph_payload(),
        )


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
    entity_info: dict[str, EntityInfo] = {}

    if seeds:
        visited, triples, entity_info = expand_subgraph(
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
        entity_info=entity_info,
    )
