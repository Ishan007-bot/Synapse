"""Build the vector index: embed all chunks and make the index queryable.

Run after ingestion (Neo4j up, no LLM key needed):
    cd backend
    python -m app.retrieval.build_index
"""
from __future__ import annotations

from ..console import enable_utf8
from ..db import Neo4jClient
from ..embeddings import Embedder
from .vector_store import backfill_embeddings, ensure_vector_index


def main() -> None:
    enable_utf8()
    print("=== Synapse vector index build ===")
    print("loading embedding model (first run downloads it)...")
    embedder = Embedder()
    print(f"  model = {embedder.model_name}  (dim={embedder.dimension})")

    with Neo4jClient() as client:
        ensure_vector_index(client, embedder.dimension)
        print("  vector index ensured")
        print("  embedding chunks...")
        count = backfill_embeddings(client, embedder)
        client.query("CALL db.awaitIndexes(300)")
        total = client.query("MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n")[0]["n"]

    print(f"  embedded this run : {count}")
    print(f"  chunks with vector: {total}")
    print("done — vector search is ready.")


if __name__ == "__main__":
    main()
