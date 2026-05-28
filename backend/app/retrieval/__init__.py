"""Retrieval: vector index management and semantic search over chunks + entities."""
from .vector_store import (
    ENTITY_INDEX_NAME,
    INDEX_NAME,
    LinkedEntity,
    RetrievedChunk,
    backfill_embeddings,
    backfill_entity_embeddings,
    ensure_entity_vector_index,
    ensure_vector_index,
    entity_vector_search,
    vector_search,
)

__all__ = [
    "ENTITY_INDEX_NAME",
    "INDEX_NAME",
    "LinkedEntity",
    "RetrievedChunk",
    "backfill_embeddings",
    "backfill_entity_embeddings",
    "ensure_entity_vector_index",
    "ensure_vector_index",
    "entity_vector_search",
    "vector_search",
]
