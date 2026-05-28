"""Tests for the subgraph payload builder on HybridContext.

These are pure-Python tests — we construct a HybridContext by hand and check
that ``subgraph_payload()`` produces the expected nodes/edges/degree/seed
flags. No Neo4j or LLM required.
"""
from __future__ import annotations

from app.retrieval.entity_linker import SeedEntity
from app.retrieval.graph_traversal import EntityInfo, Triple
from app.retrieval.hybrid import HybridContext
from app.retrieval.vector_store import RetrievedChunk


def _ctx(triples, seeds, entity_info, chunks=None):
    return HybridContext(
        chunks=chunks or [],
        triples=triples,
        seed_entities=seeds,
        visited_entity_ids={i for i in entity_info},
        entity_info=entity_info,
    )


def test_payload_marks_seeds_and_counts_degree():
    info = {
        "a": EntityInfo("a", "OpenAI", "Organization"),
        "b": EntityInfo("b", "Sam Altman", "Person"),
        "c": EntityInfo("c", "San Francisco", "Place"),
    }
    triples = [
        Triple("OpenAI", "a", "FOUNDED_BY", "Sam Altman", "b"),
        Triple("OpenAI", "a", "BASED_IN", "San Francisco", "c"),
    ]
    seeds = [SeedEntity(id="a", name="OpenAI", type="Organization", score=1.0, via="alias")]
    payload = _ctx(triples, seeds, info).subgraph_payload()

    by_id = {n.id: n for n in payload.nodes}
    assert by_id["a"].is_seed is True
    assert by_id["b"].is_seed is False
    assert by_id["c"].is_seed is False
    assert by_id["a"].degree == 2     # touched by both edges
    assert by_id["b"].degree == 1
    assert by_id["c"].degree == 1
    assert payload.seed_ids == ["a"]
    assert len(payload.edges) == 2


def test_payload_includes_seed_even_with_no_edges():
    # Seeds we linked to should appear even if no triples got expanded yet.
    info: dict[str, EntityInfo] = {}
    seeds = [SeedEntity(id="z", name="Lonely Entity", type="Concept", score=0.9, via="vector")]
    payload = _ctx([], seeds, info).subgraph_payload()
    assert len(payload.nodes) == 1
    assert payload.nodes[0].id == "z" and payload.nodes[0].is_seed is True
    assert payload.edges == []
    assert payload.seed_ids == ["z"]


def test_to_answer_assembles_sources_and_chunks():
    info = {"a": EntityInfo("a", "OpenAI", "Organization")}
    triples = [Triple("OpenAI", "a", "FOUNDED_BY", "Sam Altman", "a")]
    chunks = [
        RetrievedChunk(id="c1", text="OpenAI was founded...", source="OpenAI", score=0.91),
        RetrievedChunk(id="c2", text="Sam Altman ...", source="Sam Altman", score=0.0),  # via-entity
        RetrievedChunk(id="c3", text="More OpenAI ...", source="OpenAI", score=0.85),    # dup source
    ]
    seeds = [SeedEntity(id="a", name="OpenAI", type="Organization", score=1.0, via="alias")]
    ctx = _ctx(triples, seeds, info, chunks=chunks)
    answer = ctx.to_answer("OpenAI was founded by Sam Altman. [OpenAI]")

    assert answer.answer.startswith("OpenAI was founded")
    # Unique by source, in order
    assert [s.name for s in answer.sources] == ["OpenAI", "Sam Altman"]
    # Vector vs entity tagging
    assert answer.sources[0].via == "vector" and answer.sources[0].score == 0.91
    assert answer.sources[1].via == "entity" and answer.sources[1].score == 0.0
    # All chunks included as previews
    assert [c.id for c in answer.chunks] == ["c1", "c2", "c3"]
    # Subgraph carries through
    assert len(answer.subgraph.nodes) == 1
