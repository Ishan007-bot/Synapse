"""Shared response schemas.

These Pydantic models are the contract between the RAG core, the FastAPI layer
(Phase 6), and the frontend (Phase 7). Keeping them here means the CLI, the
HTTP API, and any downstream consumer (eval, tests) all see the same shape.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Subgraph payload (for the frontend visualization) ─────────────────────


class GraphNode(BaseModel):
    id: str
    name: str
    type: str
    is_seed: bool = False
    degree: int = 0  # number of returned-subgraph edges touching this node


class GraphEdge(BaseModel):
    source: str  # entity id
    target: str  # entity id
    predicate: str


class SubgraphPayload(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    seed_ids: list[str] = Field(default_factory=list)


# ── Source citations + chunk previews (for the chat UI) ───────────────────


class SourceInfo(BaseModel):
    name: str
    score: float = 0.0  # 0.0 means "found via entity, not vector"
    via: str = "vector"  # "vector" | "entity"


class ChunkInfo(BaseModel):
    id: str
    source: str
    text: str
    score: float = 0.0


# ── Top-level RAG response ────────────────────────────────────────────────


class RAGAnswer(BaseModel):
    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)
    chunks: list[ChunkInfo] = Field(default_factory=list)
    subgraph: SubgraphPayload = Field(default_factory=SubgraphPayload)
