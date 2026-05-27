"""Phase 0 smoke test.

Verifies the two external dependencies are wired up correctly:
  1. The configured LLM provider (Groq/Gemini) can answer a prompt.
  2. Neo4j is reachable and runs a query.

Run from the project root (with .env filled in and Neo4j up):
    python -m app.smoke        # from inside backend/
or
    python -m backend.app.smoke # from project root, if backend is a package
"""
from __future__ import annotations

import sys

from .config import settings
from .console import enable_utf8
from .db import Neo4jClient
from .llm import Message, get_provider


def check_llm() -> bool:
    print(f"[LLM] provider = {settings.llm_provider}")
    try:
        provider = get_provider()
        reply = provider.generate(
            [Message(role="user", content="Reply with a short one-sentence greeting.")],
            max_tokens=50,
        )
        print(f"[LLM] OK  -> {reply.strip()}")
        return True
    except Exception as exc:  # noqa: BLE001 - smoke test wants the message, not a crash
        print(f"[LLM] FAILED -> {type(exc).__name__}: {exc}")
        return False


def check_neo4j() -> bool:
    print(f"[Neo4j] uri = {settings.neo4j_uri}")
    try:
        with Neo4jClient() as client:
            client.verify()
            rows = client.query("RETURN 'graph-rag' AS project, 1 AS ok")
        print(f"[Neo4j] OK  -> {rows[0]}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[Neo4j] FAILED -> {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    enable_utf8()
    print("=== Synapse (Graph RAG) — Phase 0 smoke test ===")
    llm_ok = check_llm()
    neo4j_ok = check_neo4j()
    print("======================================")
    if llm_ok and neo4j_ok:
        print("All checks passed. Phase 0 is wired up correctly.")
        return 0
    print("One or more checks failed — see messages above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
