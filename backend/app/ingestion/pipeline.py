"""Ingestion pipeline: fetch -> chunk -> store in Neo4j.

Graph shape after ingestion:
    (:Document {title, url, num_chunks})-[:HAS_CHUNK]->(:Chunk {id, text, chunk_index, source})

Run it (Neo4j must be up; no LLM key needed for this phase):
    cd backend
    python -m app.ingestion.pipeline                 # full corpus
    python -m app.ingestion.pipeline --limit 3        # quick test
    python -m app.ingestion.pipeline --reset          # wipe docs/chunks first
"""
from __future__ import annotations

import argparse

from ..config import settings
from ..db import Neo4jClient
from .chunker import split_text
from .corpus import CORPUS
from .wikipedia_loader import Document, fetch_article


def ensure_schema(client: Neo4jClient) -> None:
    """Uniqueness constraints (also create backing indexes for fast MERGE)."""
    client.query(
        "CREATE CONSTRAINT document_title IF NOT EXISTS "
        "FOR (d:Document) REQUIRE d.title IS UNIQUE"
    )
    client.query(
        "CREATE CONSTRAINT chunk_id IF NOT EXISTS "
        "FOR (c:Chunk) REQUIRE c.id IS UNIQUE"
    )


def reset(client: Neo4jClient) -> None:
    """Remove previously ingested documents and chunks (leaves other data alone)."""
    client.query("MATCH (n) WHERE n:Document OR n:Chunk DETACH DELETE n")


def store_document(client: Neo4jClient, doc: Document, chunks: list[str]) -> None:
    """Upsert one document and its chunks (idempotent: replaces old chunks)."""
    # Drop any stale chunks from a previous run so re-ingesting is clean.
    client.query(
        "MATCH (d:Document {title: $title})-[:HAS_CHUNK]->(c:Chunk) DETACH DELETE c",
        title=doc.title,
    )
    client.query(
        "MERGE (d:Document {title: $title}) "
        "SET d.url = $url, d.num_chunks = $num_chunks",
        title=doc.title,
        url=doc.url,
        num_chunks=len(chunks),
    )
    rows = [
        {"id": f"{doc.title}::{i}", "index": i, "text": chunk}
        for i, chunk in enumerate(chunks)
    ]
    client.query(
        """
        MATCH (d:Document {title: $title})
        UNWIND $rows AS row
        MERGE (c:Chunk {id: row.id})
        SET c.text = row.text, c.chunk_index = row.index, c.source = $title
        MERGE (d)-[:HAS_CHUNK]->(c)
        """,
        title=doc.title,
        rows=rows,
    )


def ingest(
    titles: list[str],
    *,
    chunk_size: int,
    chunk_overlap: int,
    do_reset: bool = False,
) -> dict:
    """Run the full pipeline and return summary counts."""
    with Neo4jClient() as client:
        ensure_schema(client)
        if do_reset:
            reset(client)
            print("[reset] cleared existing documents and chunks")

        total_chunks = 0
        missing: list[str] = []
        for title in titles:
            doc = fetch_article(title)
            if doc is None:
                missing.append(title)
                print(f"  ! not found on Wikipedia: {title}")
                continue
            chunks = split_text(doc.text, chunk_size, chunk_overlap)
            store_document(client, doc, chunks)
            total_chunks += len(chunks)
            print(f"  ok {doc.title}: {len(chunks)} chunks")

        docs = client.query("MATCH (d:Document) RETURN count(d) AS n")[0]["n"]
        chunks_in_db = client.query("MATCH (c:Chunk) RETURN count(c) AS n")[0]["n"]

    return {
        "ingested_chunks": total_chunks,
        "documents_in_db": docs,
        "chunks_in_db": chunks_in_db,
        "missing": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the Wikipedia corpus into Neo4j.")
    parser.add_argument("--limit", type=int, default=None, help="only ingest the first N titles")
    parser.add_argument("--reset", action="store_true", help="wipe existing docs/chunks first")
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--chunk-overlap", type=int, default=settings.chunk_overlap)
    args = parser.parse_args()

    titles = CORPUS[: args.limit] if args.limit else CORPUS
    print(f"=== Synapse ingestion — {len(titles)} article(s) ===")
    summary = ingest(
        titles,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        do_reset=args.reset,
    )
    print("=== summary ===")
    print(f"  documents in db : {summary['documents_in_db']}")
    print(f"  chunks in db    : {summary['chunks_in_db']}")
    if summary["missing"]:
        print(f"  missing titles  : {summary['missing']}")


if __name__ == "__main__":
    main()
