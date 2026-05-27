"""Neo4j vector index: create it, fill in chunk embeddings, and search.

We keep everything in Neo4j (no separate vector DB): each :Chunk gets an
`embedding` property and a native vector index powers cosine top-k search.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db import Neo4jClient
from ..embeddings import Embedder

INDEX_NAME = "chunk_embedding"


@dataclass
class RetrievedChunk:
    id: str
    text: str
    source: str
    score: float


def ensure_vector_index(client: Neo4jClient, dimension: int) -> None:
    """Create the cosine vector index over :Chunk(embedding) if it doesn't exist."""
    client.query(
        f"CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS "
        f"FOR (c:Chunk) ON (c.embedding) "
        f"OPTIONS {{ indexConfig: {{ "
        f"`vector.dimensions`: {int(dimension)}, "
        f"`vector.similarity_function`: 'cosine' }} }}"
    )


def backfill_embeddings(
    client: Neo4jClient,
    embedder: Embedder,
    batch_size: int = 128,
) -> int:
    """Embed every :Chunk that has no embedding yet. Returns how many were embedded."""
    pending = client.query(
        "MATCH (c:Chunk) WHERE c.embedding IS NULL "
        "RETURN c.id AS id, c.text AS text"
    )
    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        vectors = embedder.embed_documents([row["text"] for row in batch])
        rows = [{"id": row["id"], "embedding": vec} for row, vec in zip(batch, vectors)]
        client.query(
            "UNWIND $rows AS row "
            "MATCH (c:Chunk {id: row.id}) "
            "SET c.embedding = row.embedding",
            rows=rows,
        )
    return len(pending)


def vector_search(
    client: Neo4jClient,
    embedder: Embedder,
    query: str,
    k: int = 5,
) -> list[RetrievedChunk]:
    """Return the top-k most semantically similar chunks to `query`."""
    query_vector = embedder.embed_query(query)
    rows = client.query(
        f"CALL db.index.vector.queryNodes('{INDEX_NAME}', $k, $qv) "
        "YIELD node, score "
        "RETURN node.id AS id, node.text AS text, node.source AS source, score "
        "ORDER BY score DESC",
        k=k,
        qv=query_vector,
    )
    return [
        RetrievedChunk(id=r["id"], text=r["text"], source=r["source"], score=r["score"])
        for r in rows
    ]
