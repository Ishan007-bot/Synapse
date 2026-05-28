"""Build the vector indexes: embed chunks AND entity names.

Run after ingestion (and after the graph build, if you want the entity index
populated too — but it's fine to run either way; it just no-ops if there are
no entities yet):
    cd backend
    python -m app.retrieval.build_index
"""
from __future__ import annotations

from ..console import enable_utf8
from ..db import Neo4jClient
from ..embeddings import Embedder
from .vector_store import (
    backfill_embeddings,
    backfill_entity_embeddings,
    ensure_entity_vector_index,
    ensure_vector_index,
)


def main() -> None:
    enable_utf8()
    print("=== Synapse vector index build ===")
    print("loading embedding model (first run downloads it)...")
    embedder = Embedder()
    print(f"  model = {embedder.model_name}  (dim={embedder.dimension})")

    with Neo4jClient() as client:
        # Chunk index — the naive-RAG baseline.
        ensure_vector_index(client, embedder.dimension)
        print("  chunk vector index ensured")
        print("  embedding chunks...")
        n_chunks = backfill_embeddings(client, embedder)

        # Entity index — used by the graph linker in Phase 4.
        ensure_entity_vector_index(client, embedder.dimension)
        print("  entity vector index ensured")
        print("  embedding entity names...")
        n_entities = backfill_entity_embeddings(client, embedder)

        client.query("CALL db.awaitIndexes(300)")
        chunks_with_vec = client.query(
            "MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n"
        )[0]["n"]
        entities_with_vec = client.query(
            "MATCH (e:Entity) WHERE e.embedding IS NOT NULL RETURN count(e) AS n"
        )[0]["n"]

    print(f"  embedded this run : {n_chunks} chunks, {n_entities} entities")
    print(f"  with vectors      : {chunks_with_vec} chunks, {entities_with_vec} entities")
    print("done.")


if __name__ == "__main__":
    main()
