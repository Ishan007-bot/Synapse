"""Map a natural-language query to seed entities in the knowledge graph.

This is the first step of Graph RAG: before we can traverse the graph we have
to pick where to start. Two signals combined:

1. **Vector similarity** between the query and entity names (catches semantic
   matches even when the user paraphrases — "Bengio's PhD advisor" picks up
   "Yoshua Bengio").
2. **Alias / substring match** (catches exact mentions the embedding might
   miss, especially for short acronyms like "BERT" or "GPT").

We deduplicate by entity id and return the union ordered by confidence.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db import Neo4jClient
from ..embeddings import Embedder
from .vector_store import LinkedEntity, entity_vector_search


@dataclass
class SeedEntity:
    id: str
    name: str
    type: str
    score: float  # 1.0 for exact alias match, vector cosine sim otherwise
    via: str  # "vector" or "alias"


def _alias_match(client: Neo4jClient, query: str, min_token_length: int = 4) -> list[SeedEntity]:
    """Find entities whose canonical name or any alias appears in the query."""
    # We pass the lower-cased query and let Cypher do the containment check.
    # The min length guards against false positives on short names like "AI" / "ML".
    rows = client.query(
        """
        MATCH (e:Entity)
        WHERE size(e.name) >= $min_len
        AND (toLower($q) CONTAINS toLower(e.name)
             OR any(a IN e.aliases WHERE size(a) >= $min_len AND toLower($q) CONTAINS toLower(a)))
        RETURN e.id AS id, e.name AS name, e.type AS type
        """,
        q=query,
        min_len=min_token_length,
    )
    return [SeedEntity(id=r["id"], name=r["name"], type=r["type"], score=1.0, via="alias") for r in rows]


def link_entities(
    client: Neo4jClient,
    embedder: Embedder,
    query: str,
    *,
    k_vector: int = 5,
    vector_score_threshold: float = 0.55,
) -> list[SeedEntity]:
    """Combine vector-similar entities with any alias matches."""
    # Vector candidates above a threshold (avoid pulling in noise).
    vector_hits: list[LinkedEntity] = entity_vector_search(client, embedder, query, k=k_vector)
    vector_seeds = [
        SeedEntity(id=v.id, name=v.name, type=v.type, score=v.score, via="vector")
        for v in vector_hits
        if v.score >= vector_score_threshold
    ]
    alias_seeds = _alias_match(client, query)

    # Merge by id; prefer the higher-confidence record.
    by_id: dict[str, SeedEntity] = {}
    for s in vector_seeds + alias_seeds:
        existing = by_id.get(s.id)
        if existing is None or s.score > existing.score:
            by_id[s.id] = s
    return sorted(by_id.values(), key=lambda s: s.score, reverse=True)
