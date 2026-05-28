"""FastAPI app exposing Synapse Graph RAG over HTTP.

Endpoints (the Phase 7 Next.js frontend will consume these):

  GET  /health                          - liveness check
  GET  /stats                           - corpus + graph counts
  GET  /graph?limit_nodes=200           - full knowledge graph (top-N by degree)
  GET  /graph/subgraph?question=...     - retrieved subgraph for a question (no LLM)
  POST /query                           - Graph RAG (blocking) -> RAGAnswer JSON
  POST /query/stream                    - Graph RAG (SSE token stream + final payload)
  POST /query/naive                     - vector-only baseline (for side-by-side comparison)

Try it: open http://localhost:8000/docs for Swagger UI.
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from ..graph_rag import GraphRAG
from ..schemas import (
    ChunkInfo,
    GraphEdge,
    GraphNode,
    RAGAnswer,
    SourceInfo,
    SubgraphPayload,
)

logger = logging.getLogger(__name__)


# ── Shared resources (heavy: embedder, Neo4j driver) ──────────────────────
# We hold a single GraphRAG instance for the app's lifetime so we don't
# reload the sentence-transformers model or reconnect to Neo4j per request.


class _AppState:
    rag: GraphRAG | None = None


state = _AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting Synapse API; instantiating GraphRAG (loads embedder, opens Neo4j)")
    state.rag = GraphRAG()
    try:
        yield
    finally:
        if state.rag is not None:
            state.rag.close()
            logger.info("Neo4j connection closed")


def _rag() -> GraphRAG:
    if state.rag is None:
        raise HTTPException(status_code=503, detail="RAG system not ready")
    return state.rag


# ── App ───────────────────────────────────────────────────────────────────


app = FastAPI(
    title="Synapse Graph RAG API",
    description=(
        "Knowledge-graph-augmented retrieval over a Wikipedia AI-field corpus. "
        "Combines vector search with N-hop graph traversal so multi-hop questions "
        "(answered across multiple articles) work where naive RAG fails."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# Permissive CORS for local development (Next.js defaults to :3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all so the frontend always gets clean JSON, never an HTML 500 page."""
    logger.exception("unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})


# ── Request / response models ─────────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural-language question")
    hops: int = Field(default=2, ge=0, le=4, description="Graph traversal depth")
    k_chunks: int = Field(default=5, ge=1, le=20, description="Top-k chunks to retrieve")


class NaiveQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class NaiveAnswer(BaseModel):
    answer: str
    sources: list[SourceInfo] = Field(default_factory=list)
    chunks: list[ChunkInfo] = Field(default_factory=list)


class Stats(BaseModel):
    documents: int
    chunks: int
    chunks_with_vector: int
    entities: int
    entities_with_vector: int
    entity_relations: int
    mentions: int


# ── Endpoints ─────────────────────────────────────────────────────────────


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "service": "synapse"}


@app.get("/stats", response_model=Stats, tags=["system"])
def stats() -> Stats:
    """Counts you'd want in a dashboard header."""
    c = _rag().client
    docs = c.query("MATCH (d:Document) RETURN count(d) AS n")[0]["n"]
    chunks = c.query("MATCH (c:Chunk) RETURN count(c) AS n")[0]["n"]
    chunks_vec = c.query("MATCH (c:Chunk) WHERE c.embedding IS NOT NULL RETURN count(c) AS n")[0]["n"]
    ents = c.query("MATCH (e:Entity) RETURN count(e) AS n")[0]["n"]
    ents_vec = c.query("MATCH (e:Entity) WHERE e.embedding IS NOT NULL RETURN count(e) AS n")[0]["n"]
    rels = c.query(
        "MATCH (:Entity)-[r]->(:Entity) WHERE type(r) <> 'MENTIONED_IN' RETURN count(r) AS n"
    )[0]["n"]
    mentions = c.query("MATCH (:Entity)-[r:MENTIONED_IN]->(:Chunk) RETURN count(r) AS n")[0]["n"]
    return Stats(
        documents=docs,
        chunks=chunks,
        chunks_with_vector=chunks_vec,
        entities=ents,
        entities_with_vector=ents_vec,
        entity_relations=rels,
        mentions=mentions,
    )


@app.post("/query", response_model=RAGAnswer, tags=["rag"])
def query(req: QueryRequest) -> RAGAnswer:
    """Blocking Graph RAG query. Returns the full structured answer."""
    return _rag().answer(req.question, hops=req.hops, k_chunks=req.k_chunks)


@app.post("/query/stream", tags=["rag"])
def query_stream(req: QueryRequest) -> StreamingResponse:
    """Streaming Graph RAG over Server-Sent Events.

    Event sequence:
      - ``context`` (once): subgraph + sources, so the frontend can render the
        graph viz while the answer is still streaming in.
      - ``token`` (many): each LLM delta, in order.
      - ``done`` (once): the full ``RAGAnswer`` payload with the assembled
        answer text.
      - ``error`` (only on failure): ``{"message": "..."}``.
    """
    rag = _rag()

    def gen():
        try:
            tokens, context = rag.stream(req.question, hops=req.hops, k_chunks=req.k_chunks)
        except Exception as exc:  # noqa: BLE001 - any retrieval failure becomes an SSE error
            logger.exception("retrieval failed for streaming query")
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
            return

        # Emit context first (frontend can render the graph immediately).
        partial = context.to_answer("")
        yield _sse(
            "context",
            {
                "sources": [s.model_dump() for s in partial.sources],
                "chunks": [c.model_dump() for c in partial.chunks],
                "subgraph": partial.subgraph.model_dump(),
            },
        )

        buf: list[str] = []
        try:
            for tok in tokens:
                buf.append(tok)
                yield _sse("token", {"text": tok})
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM stream failed mid-response")
            yield _sse("error", {"message": f"{type(exc).__name__}: {exc}"})
            return

        final = context.to_answer("".join(buf))
        yield _sse("done", final.model_dump())

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/query/naive", response_model=NaiveAnswer, tags=["rag"])
def query_naive(req: NaiveQueryRequest) -> NaiveAnswer:
    """Vector-only baseline (no graph) — for the side-by-side comparison demo."""
    rag = _rag()
    text, chunks = rag.naive_answer(req.question, k=req.k)
    seen: set[str] = set()
    sources: list[SourceInfo] = []
    chunk_infos: list[ChunkInfo] = []
    for c in chunks:
        chunk_infos.append(ChunkInfo(id=c.id, source=c.source, text=c.text, score=c.score))
        if c.source not in seen:
            sources.append(SourceInfo(name=c.source, score=c.score, via="vector"))
            seen.add(c.source)
    return NaiveAnswer(answer=text, sources=sources, chunks=chunk_infos)


@app.get("/graph", response_model=SubgraphPayload, tags=["graph"])
def full_graph(
    limit_nodes: int = Query(200, ge=10, le=2000, description="cap on returned nodes (top by degree)"),
    min_degree: int = Query(1, ge=0, description="exclude entities with degree below this"),
) -> SubgraphPayload:
    """Return the full knowledge graph (top-N entities by degree + their edges)."""
    c = _rag().client
    nodes_rows = c.query(
        """
        MATCH (e:Entity)
        OPTIONAL MATCH (e)-[r]-(:Entity)
        WITH e, count(CASE WHEN type(r) <> 'MENTIONED_IN' THEN r END) AS deg
        WHERE deg >= $min_deg
        RETURN e.id AS id, e.name AS name, e.type AS type, deg AS degree
        ORDER BY deg DESC
        LIMIT $limit
        """,
        limit=limit_nodes,
        min_deg=min_degree,
    )
    nodes = [
        GraphNode(id=r["id"], name=r["name"], type=r["type"], is_seed=False, degree=r["degree"])
        for r in nodes_rows
    ]
    if not nodes:
        return SubgraphPayload(nodes=[], edges=[], seed_ids=[])

    node_ids = [n.id for n in nodes]
    edges_rows = c.query(
        """
        MATCH (a:Entity)-[r]->(b:Entity)
        WHERE a.id IN $ids AND b.id IN $ids AND type(r) <> 'MENTIONED_IN'
        RETURN a.id AS source, b.id AS target, type(r) AS predicate
        """,
        ids=node_ids,
    )
    edges = [
        GraphEdge(source=r["source"], target=r["target"], predicate=r["predicate"])
        for r in edges_rows
    ]
    return SubgraphPayload(nodes=nodes, edges=edges, seed_ids=[])


@app.get("/graph/subgraph", response_model=RAGAnswer, tags=["graph"])
def question_subgraph(
    question: str = Query(..., min_length=1),
    hops: int = Query(2, ge=0, le=4),
) -> RAGAnswer:
    """The subgraph the system would use for a given question — no LLM call."""
    context = _rag().retrieve(question, hops=hops)
    return context.to_answer("")


# ── SSE helper ────────────────────────────────────────────────────────────


def _sse(event: str, data: dict | None = None) -> str:
    payload = json.dumps(data or {}, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"
