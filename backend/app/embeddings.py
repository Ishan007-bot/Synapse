"""Local embedding model (sentence-transformers).

Runs entirely on the machine — no API, no rate limits, no cost. We default to
BAAI/bge-small-en-v1.5 (384 dims): small, fast, and strong on retrieval.

Embeddings are L2-normalized, so cosine similarity (what the Neo4j vector index
uses) is well-behaved. Following BGE's guidance, only the *query* is prefixed
with an instruction; document chunks are embedded as-is.
"""
from __future__ import annotations

from sentence_transformers import SentenceTransformer

from .config import settings


class Embedder:
    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model = SentenceTransformer(self.model_name)

    @property
    def dimension(self) -> int:
        # Method was renamed across sentence-transformers versions; support both.
        getter = getattr(self._model, "get_embedding_dimension", None)
        return getter() if getter else self._model.get_sentence_embedding_dimension()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=64,
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        vector = self._model.encode(
            settings.query_instruction + text,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()
