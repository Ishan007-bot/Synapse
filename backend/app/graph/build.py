"""Build the knowledge graph: extract per document, resolve, write to Neo4j.

Run after ingestion (Neo4j up, LLM key in .env):
    cd backend
    python -m app.graph.build --limit 3       # try on 3 docs first
    python -m app.graph.build --reset         # full corpus, wipe old entities first
    python -m app.graph.build --no-cache      # ignore disk cache and re-extract

Document text is reconstructed by concatenating its chunks in order. Chunks
overlap slightly (Phase 1), which adds a little noise to the input but doesn't
hurt extraction in practice.
"""
from __future__ import annotations

import argparse
import time

from ..console import enable_utf8
from ..db import Neo4jClient
from ..llm import get_provider
from . import cache
from .extraction import extract_from_document
from .resolution import Resolver
from .store import ensure_schema, link_mentions, reset_graph, write_entities, write_relations


def _reconstruct_text(client: Neo4jClient, title: str) -> str:
    rows = client.query(
        "MATCH (d:Document {title: $title})-[:HAS_CHUNK]->(c:Chunk) "
        "RETURN c.text AS text ORDER BY c.chunk_index",
        title=title,
    )
    return "\n".join(r["text"] for r in rows)


def main() -> None:
    enable_utf8()
    parser = argparse.ArgumentParser(description="Build the knowledge graph in Neo4j.")
    parser.add_argument("--limit", type=int, default=None, help="only process the first N documents")
    parser.add_argument("--reset", action="store_true", help="wipe existing entities/relations first")
    parser.add_argument("--no-cache", action="store_true", help="ignore disk cache and re-extract")
    parser.add_argument(
        "--provider",
        default=None,
        choices=["groq", "gemini"],
        help="override LLM_PROVIDER for this run (Gemini's free TPM handles big articles better)",
    )
    args = parser.parse_args()

    provider = get_provider(args.provider)
    print(f"using LLM provider: {provider.name}")
    resolver = Resolver()
    pending_relations: list[dict] = []

    with Neo4jClient() as client:
        ensure_schema(client)
        if args.reset:
            reset_graph(client)
            print("[reset] cleared existing entities and relations")

        titles = [
            r["title"]
            for r in client.query("MATCH (d:Document) RETURN d.title AS title ORDER BY d.title")
        ]
        if args.limit:
            titles = titles[: args.limit]

        print(f"=== Synapse graph build — {len(titles)} document(s) ===")
        t0 = time.time()

        for title in titles:
            result = None if args.no_cache else cache.get(title)
            if result is not None:
                tag = "cache"
            else:
                text = _reconstruct_text(client, title)
                if not text:
                    print(f"  ! no text for {title}; skipping")
                    continue
                result = extract_from_document(title, text, provider)
                # Only cache real results — caching empties would silently lock in failures
                # (the next run would skip the doc instead of retrying).
                if result.entities:
                    cache.put(title, result)
                    tag = "ok"
                else:
                    tag = "FAIL"
            print(
                f"  {tag} {title}: "
                f"{len(result.entities)} entities, {len(result.relations)} relations"
            )

            # Map this doc's raw names to canonical entities.
            name_to_entity: dict[str, str] = {}
            for ent in result.entities:
                canonical = resolver.add(ent.name, ent.type, source_doc=title)
                if canonical is not None:
                    name_to_entity[ent.name] = canonical.id

            for rel in result.relations:
                src_id = name_to_entity.get(rel.source)
                tgt_id = name_to_entity.get(rel.target)
                if src_id and tgt_id and src_id != tgt_id:
                    pending_relations.append(
                        {"source_id": src_id, "target_id": tgt_id, "type": rel.type, "doc": title}
                    )

        print("\nwriting graph to Neo4j...")
        n_ent = write_entities(client, resolver.all())
        n_rel = write_relations(client, pending_relations)
        n_mention = link_mentions(client, resolver.all())

        # Final stats from the DB
        ne = client.query("MATCH (e:Entity) RETURN count(e) AS n")[0]["n"]
        nr = client.query(
            "MATCH (:Entity)-[r]->(:Entity) WHERE type(r) <> 'MENTIONED_IN' RETURN count(r) AS n"
        )[0]["n"]
        nm = client.query("MATCH (:Entity)-[r:MENTIONED_IN]->(:Chunk) RETURN count(r) AS n")[0]["n"]
        top = client.query(
            "MATCH (e:Entity)-[r]-(:Entity) "
            "RETURN e.name AS name, e.type AS type, count(r) AS degree "
            "ORDER BY degree DESC LIMIT 5"
        )

        print(f"\n=== summary ===")
        print(f"  written this run : {n_ent} entities, {n_rel} relations, {n_mention} mentions")
        print(f"  total in db      : {ne} entities, {nr} entity-entity relations, {nm} mentions")
        print(f"  top entities     :")
        for row in top:
            print(f"      {row['name']:35} [{row['type']}]  degree={row['degree']}")
        print(f"  elapsed          : {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
