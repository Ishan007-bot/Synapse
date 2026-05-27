"""Retrieval: vector index management and semantic search over chunks."""
from .vector_store import (
    INDEX_NAME,
    backfill_embeddings,
    ensure_vector_index,
    vector_search,
)

__all__ = ["INDEX_NAME", "backfill_embeddings", "ensure_vector_index", "vector_search"]
