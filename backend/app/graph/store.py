"""Neo4j writes for the knowledge graph.

Schema added by this module:
  (:Entity {id, name, type, aliases})-[:<DYNAMIC_REL_TYPE>]->(:Entity)
  (:Entity)-[:MENTIONED_IN]->(:Chunk)

Dynamic relationship types use APOC (``apoc.merge.relationship``), which is
loaded in our docker-compose.
"""
from __future__ import annotations

from collections.abc import Iterable

from ..db import Neo4jClient
from .resolution import CanonicalEntity


def ensure_schema(client: Neo4jClient) -> None:
    client.query(
        "CREATE CONSTRAINT entity_id IF NOT EXISTS "
        "FOR (e:Entity) REQUIRE e.id IS UNIQUE"
    )


def reset_graph(client: Neo4jClient) -> None:
    """Wipe entities and their relationships, leaving Documents/Chunks alone."""
    client.query("MATCH (e:Entity) DETACH DELETE e")


def write_entities(client: Neo4jClient, entities: Iterable[CanonicalEntity]) -> int:
    rows = [
        {
            "id": e.id,
            "name": e.name,
            "type": e.type,
            "aliases": sorted(e.aliases),
            "mention_docs": sorted(e.mention_docs),
        }
        for e in entities
    ]
    if not rows:
        return 0
    client.query(
        """
        UNWIND $rows AS row
        MERGE (e:Entity {id: row.id})
        SET e.name = row.name,
            e.type = row.type,
            e.aliases = row.aliases,
            e.mention_docs = row.mention_docs
        """,
        rows=rows,
    )
    return len(rows)


def write_relations(client: Neo4jClient, relations: list[dict]) -> int:
    """Each row: {source_id, target_id, type, doc}. Uses APOC for dynamic rel type."""
    if not relations:
        return 0
    client.query(
        """
        UNWIND $rows AS row
        MATCH (a:Entity {id: row.source_id})
        MATCH (b:Entity {id: row.target_id})
        CALL apoc.merge.relationship(a, row.type, {}, {doc: row.doc}, b) YIELD rel
        RETURN count(rel)
        """,
        rows=relations,
    )
    return len(relations)


def link_mentions(
    client: Neo4jClient,
    entities: list[CanonicalEntity],
    *,
    min_name_length: int = 4,
    batch_size: int = 2000,
) -> int:
    """Create (:Entity)-[:MENTIONED_IN]->(:Chunk) edges via text containment.

    Done in Python (one pass over all chunks) rather than per-entity Cypher
    so we avoid an O(entities * chunks) round-trip.
    """
    chunks = client.query("MATCH (c:Chunk) RETURN c.id AS id, toLower(c.text) AS text")
    # Pre-lowercase entity names and skip very short ones (would over-match, e.g. "AI").
    candidates: list[tuple[str, str]] = [
        (e.id, e.name.lower()) for e in entities if len(e.name) >= min_name_length
    ]

    edges: list[dict] = []
    for chunk in chunks:
        text = chunk["text"]
        cid = chunk["id"]
        for eid, name_lc in candidates:
            if name_lc in text:
                edges.append({"eid": eid, "cid": cid})

    for start in range(0, len(edges), batch_size):
        batch = edges[start : start + batch_size]
        client.query(
            """
            UNWIND $rows AS row
            MATCH (e:Entity {id: row.eid})
            MATCH (c:Chunk {id: row.cid})
            MERGE (e)-[:MENTIONED_IN]->(c)
            """,
            rows=batch,
        )
    return len(edges)
