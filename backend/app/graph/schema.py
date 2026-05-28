"""Pydantic models for the extraction output and our entity ontology.

A small, *closed* set of entity types is the most important constraint: it
keeps the resulting graph clean and queryable. Relation types are looser
(any UPPER_SNAKE_CASE label is accepted) because the LLM picks reasonable
predicates on its own and over-constraining hurts recall.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

# Closed ontology — anything the LLM proposes outside this list is mapped to "Concept".
ENTITY_TYPES: tuple[str, ...] = (
    "Person",
    "Organization",
    "Model",
    "Method",
    "Concept",
    "Place",
    "Event",
    "Field",
    "Award",
)


class Entity(BaseModel):
    name: str
    type: str

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("entity name must not be empty")
        return v

    @field_validator("type")
    @classmethod
    def _coerce_type(cls, v: str) -> str:
        v = (v or "").strip().title()
        return v if v in ENTITY_TYPES else "Concept"


class Relation(BaseModel):
    source: str
    target: str
    type: str

    @field_validator("source", "target")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("relation endpoints must not be empty")
        return v

    @field_validator("type")
    @classmethod
    def _normalize_type(cls, v: str) -> str:
        # Force UPPER_SNAKE_CASE labels for clean Neo4j relationship types.
        normalized = re.sub(r"[^A-Z0-9_]", "_", (v or "").upper().strip()).strip("_")
        return normalized or "RELATED_TO"


class ExtractionResult(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
