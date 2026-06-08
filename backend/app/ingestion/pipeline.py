"""Ingestion pipeline: documents -> chunk -> store in Neo4j (-> optional embed).

Graph shape after ingestion:
    (:Document {title, url, num_chunks})-[:HAS_CHUNK]->(:Chunk {id, text, chunk_index, source})

Two ways to feed it documents:

1. The Wikipedia corpus (the default in this repo):
       python -m app.ingestion.pipeline                     # full corpus
       python -m app.ingestion.pipeline --limit 3            # quick test
       python -m app.ingestion.pipeline --reset              # wipe docs/chunks first

2. Local files / folders (your own corpus):
       python -m app.ingestion.pipeline --files notes.pdf paper.md
       python -m app.ingestion.pipeline --folder ./my-docs
       python -m app.ingestion.pipeline --files thing.pdf --embed   # also build vector index

Add ``--embed`` to also build the Neo4j vector index in the same run so the new
chunks are immediately queryable; otherwise run ``app.retrieval.build_index``
separately.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from ..config import settings
from ..console import enable_utf8
from ..db import Neo4jClient
from .chunker import split_text
from .corpus import CORPUS
from .loaders import load_file, load_folder
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


# ─────────────────────────────────────────────────────────────────────────
# Core: ingest a list of already-loaded Documents (used by CLI + HTTP).
# ─────────────────────────────────────────────────────────────────────────


def ingest_documents(
    documents: Iterable[Document],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    do_reset: bool = False,
    also_embed: bool = False,
    embedder=None,
    verbose: bool = True,
) -> dict:
    """Chunk every document and write it into Neo4j.

    When ``also_embed=True`` we also (a) ensure the vector index exists and
    (b) embed any chunks that don't yet have a vector — so newly-ingested
    documents are immediately queryable. ``embedder`` is only needed in that
    case; pass an existing Embedder instance to avoid reloading the model.
    """
    documents = list(documents)
    ingested_chunks = 0
    titles: list[str] = []

    with Neo4jClient() as client:
        ensure_schema(client)
        if do_reset:
            reset(client)
            if verbose:
                print("[reset] cleared existing documents and chunks")

        for doc in documents:
            if not doc.text or not doc.text.strip():
                if verbose:
                    print(f"  ! empty document: {doc.title}; skipping")
                continue
            chunks = split_text(doc.text, chunk_size, chunk_overlap)
            store_document(client, doc, chunks)
            ingested_chunks += len(chunks)
            titles.append(doc.title)
            if verbose:
                print(f"  ok {doc.title}: {len(chunks)} chunks")

        embedded = 0
        if also_embed and documents:
            # Lazy import — avoids loading torch when callers only need to write chunks.
            from ..embeddings import Embedder
            from ..retrieval.vector_store import (
                backfill_embeddings,
                ensure_vector_index,
            )

            emb = embedder or Embedder()
            ensure_vector_index(client, emb.dimension)
            embedded = backfill_embeddings(client, emb)
            client.query("CALL db.awaitIndexes(300)")
            if verbose:
                print(f"  embedded {embedded} new chunks")

        documents_in_db = client.query("MATCH (d:Document) RETURN count(d) AS n")[0]["n"]
        chunks_in_db = client.query("MATCH (c:Chunk) RETURN count(c) AS n")[0]["n"]

    return {
        "documents_ingested": len(titles),
        "ingested_chunks": ingested_chunks,
        "embedded": embedded,
        "documents_in_db": documents_in_db,
        "chunks_in_db": chunks_in_db,
        "titles": titles,
    }


# ─────────────────────────────────────────────────────────────────────────
# Wikipedia wrapper (kept for backwards compatibility + the default corpus).
# ─────────────────────────────────────────────────────────────────────────


def ingest_wikipedia(
    titles: list[str],
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    do_reset: bool = False,
    also_embed: bool = False,
    embedder=None,
) -> dict:
    docs: list[Document] = []
    missing: list[str] = []
    for title in titles:
        d = fetch_article(title)
        if d is None:
            missing.append(title)
            print(f"  ! not found on Wikipedia: {title}")
        else:
            docs.append(d)
    summary = ingest_documents(
        docs,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        do_reset=do_reset,
        also_embed=also_embed,
        embedder=embedder,
    )
    summary["missing"] = missing
    return summary


# ─────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────


def _load_local_documents(files: list[str] | None, folder: str | None) -> list[Document]:
    docs: list[Document] = []
    if files:
        for f in files:
            path = Path(f)
            if not path.exists():
                print(f"  ! file not found: {f}")
                continue
            doc = load_file(path)
            if doc is None:
                print(f"  ! unsupported format: {f}")
                continue
            if not doc.text.strip():
                print(f"  ! empty document: {f}")
                continue
            docs.append(doc)
    if folder:
        folder_path = Path(folder)
        if not folder_path.is_dir():
            print(f"  ! folder not found: {folder}")
        else:
            docs.extend(load_folder(folder_path))
    return docs


def main() -> None:
    enable_utf8()
    parser = argparse.ArgumentParser(description="Ingest documents into Neo4j.")
    parser.add_argument("--files", nargs="+", default=None,
                        help="ingest one or more local files (pdf/txt/md)")
    parser.add_argument("--folder", default=None,
                        help="ingest every supported file in this folder (non-recursive)")
    parser.add_argument("--embed", action="store_true",
                        help="also embed new chunks so they're immediately queryable "
                             "(otherwise run app.retrieval.build_index later)")
    parser.add_argument("--limit", type=int, default=None,
                        help="(Wikipedia mode only) ingest just the first N titles")
    parser.add_argument("--reset", action="store_true", help="wipe existing docs/chunks first")
    parser.add_argument("--chunk-size", type=int, default=settings.chunk_size)
    parser.add_argument("--chunk-overlap", type=int, default=settings.chunk_overlap)
    args = parser.parse_args()

    if args.files or args.folder:
        docs = _load_local_documents(args.files, args.folder)
        print(f"=== Synapse ingestion — {len(docs)} local document(s) ===")
        summary = ingest_documents(
            docs,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            do_reset=args.reset,
            also_embed=args.embed,
        )
    else:
        titles = CORPUS[: args.limit] if args.limit else CORPUS
        print(f"=== Synapse ingestion — {len(titles)} Wikipedia article(s) ===")
        summary = ingest_wikipedia(
            titles,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            do_reset=args.reset,
            also_embed=args.embed,
        )

    print("=== summary ===")
    print(f"  documents ingested this run : {summary.get('documents_ingested', 0)}")
    print(f"  chunks added this run       : {summary['ingested_chunks']}")
    print(f"  embedded this run           : {summary.get('embedded', 0)}")
    print(f"  documents in db (total)     : {summary['documents_in_db']}")
    print(f"  chunks in db (total)        : {summary['chunks_in_db']}")
    if summary.get("missing"):
        print(f"  missing titles              : {summary['missing']}")


if __name__ == "__main__":
    main()
