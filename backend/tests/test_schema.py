"""Tests for the extraction schema's coercion rules."""
from __future__ import annotations

import pytest

from app.graph.schema import ENTITY_TYPES, Entity, ExtractionResult, Relation


def test_unknown_entity_type_falls_back_to_concept():
    e = Entity(name="Stochastic Gradient Descent", type="Algorithm")
    assert e.type == "Concept"


def test_known_entity_types_round_trip():
    for t in ENTITY_TYPES:
        assert Entity(name=f"x_{t}", type=t).type == t


def test_entity_type_is_case_insensitive():
    assert Entity(name="OpenAI", type="organization").type == "Organization"


def test_relation_type_normalized_to_upper_snake_case():
    assert Relation(source="a", target="b", type="works at").type == "WORKS_AT"
    assert Relation(source="a", target="b", type="co-founded").type == "CO_FOUNDED"
    assert Relation(source="a", target="b", type="").type == "RELATED_TO"


def test_extraction_result_defaults_empty_lists():
    r = ExtractionResult.model_validate({})
    assert r.entities == [] and r.relations == []


def test_empty_entity_name_rejected():
    with pytest.raises(Exception):
        Entity(name="   ", type="Person")
