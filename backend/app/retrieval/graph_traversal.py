"""BFS expansion from seed entities through the knowledge graph.

Given the entities the linker found, we explore N hops out and collect the
relationships we find as triples. These triples become the "structured"
half of the retrieval context — facts the LLM can reason over directly,
which is where multi-hop questions get their answer.

We deliberately ignore :MENTIONED_IN edges here (those connect entities to
chunks, not entities to each other) and use plain Cypher so we don't depend
on extra APOC procedures for traversal.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..db import Neo4jClient


@dataclass(frozen=True)
class Triple:
    source: str
    source_id: str
    predicate: str
    target: str
    target_id: str

    def to_sentence(self) -> str:
        """Render the triple as a short readable sentence for the prompt."""
        verb = self.predicate.replace("_", " ").lower()
        return f"{self.source} {verb} {self.target}."


@dataclass(frozen=True)
class EntityInfo:
    """Minimal entity metadata gathered during traversal — used by the payload."""
    id: str
    name: str
    type: str


def expand_subgraph(
    client: Neo4jClient,
    seed_ids: list[str],
    *,
    hops: int = 2,
    max_triples: int = 60,
) -> tuple[set[str], list[Triple], dict[str, EntityInfo]]:
    """BFS expansion from the seed entities, capped at `max_triples` edges.

    Returns ``(visited_entity_ids, triples, entity_info)``. ``entity_info``
    maps each entity id we touched to its name and type — the frontend uses
    that to render the subgraph without an extra round-trip. Edges are
    de-duplicated by ``(source, predicate, target)``.
    """
    visited: set[str] = set(seed_ids)
    frontier: set[str] = set(seed_ids)
    seen_triples: set[tuple[str, str, str]] = set()
    triples: list[Triple] = []
    entity_info: dict[str, EntityInfo] = {}

    for _ in range(max(hops, 0)):
        if not frontier or len(triples) >= max_triples:
            break
        rows = client.query(
            """
            MATCH (e:Entity)-[r]-(n:Entity)
            WHERE e.id IN $ids AND type(r) <> 'MENTIONED_IN'
            RETURN e.name AS sname, e.id AS sid, e.type AS stype,
                   type(r) AS rel,
                   n.name AS nname, n.id AS nid, n.type AS ntype
            """,
            ids=list(frontier),
        )
        next_frontier: set[str] = set()
        for row in rows:
            entity_info.setdefault(row["sid"], EntityInfo(row["sid"], row["sname"], row["stype"]))
            entity_info.setdefault(row["nid"], EntityInfo(row["nid"], row["nname"], row["ntype"]))
            if len(triples) >= max_triples:
                break
            key = (row["sname"], row["rel"], row["nname"])
            if key in seen_triples:
                continue
            seen_triples.add(key)
            triples.append(
                Triple(
                    source=row["sname"],
                    source_id=row["sid"],
                    predicate=row["rel"],
                    target=row["nname"],
                    target_id=row["nid"],
                )
            )
            if row["nid"] not in visited:
                visited.add(row["nid"])
                next_frontier.add(row["nid"])
        frontier = next_frontier

    return visited, triples, entity_info


def chunks_for_entities(
    client: Neo4jClient,
    entity_ids: list[str],
    *,
    limit_per_entity: int = 3,
    total_limit: int = 15,
) -> list[dict]:
    """Pull chunks that mention any of the given entities (via :MENTIONED_IN).

    Useful for grounding the answer in source text, especially for entities
    whose own article wasn't extracted (their facts only exist as graph edges,
    so we still want the prose context they appear in).
    """
    if not entity_ids:
        return []
    rows = client.query(
        """
        UNWIND $ids AS eid
        MATCH (e:Entity {id: eid})-[:MENTIONED_IN]->(c:Chunk)
        WITH e, c
        ORDER BY c.chunk_index
        WITH e, collect(c)[..$per_entity] AS cs
        UNWIND cs AS c
        RETURN DISTINCT c.id AS id, c.text AS text, c.source AS source
        LIMIT $total
        """,
        ids=entity_ids,
        per_entity=limit_per_entity,
        total=total_limit,
    )
    return rows
