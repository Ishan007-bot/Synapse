"""Thin wrapper around the Neo4j Python driver.

Keeps a single driver instance and exposes a couple of convenience methods.
Later phases (ingestion, graph construction, retrieval) build on top of this.
"""
from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase

from ..config import settings


class Neo4jClient:
    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self._driver = GraphDatabase.driver(
            uri or settings.neo4j_uri,
            auth=(user or settings.neo4j_user, password or settings.neo4j_password),
        )

    def verify(self) -> None:
        """Raise if the database is unreachable or auth fails."""
        self._driver.verify_connectivity()

    def query(self, cypher: str, **params: Any) -> list[dict]:
        """Run a Cypher statement and return rows as dicts."""
        with self._driver.session() as session:
            result = session.run(cypher, **params)
            return [record.data() for record in result]

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Neo4jClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
