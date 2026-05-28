"""Tests for entity normalization + the Resolver."""
from __future__ import annotations

from app.graph.resolution import Resolver, normalize_name


def test_normalize_collapses_spacing_and_suffixes():
    # All of these refer to the same organization — the normalizer says so.
    assert normalize_name("OpenAI") == normalize_name("Open AI") == normalize_name("OpenAI, Inc.")


def test_normalize_handles_unicode():
    # accented forms collapse to their ASCII equivalents
    assert normalize_name("Yoshua Bengio") == normalize_name("Yoshúa Bengio")


def test_resolver_merges_aliases_within_same_type():
    r = Resolver()
    a = r.add("OpenAI", "Organization", source_doc="OpenAI")
    b = r.add("Open AI", "Organization", source_doc="Sam Altman")
    assert a is b
    assert {"OpenAI", "Open AI"} == a.aliases
    assert {"OpenAI", "Sam Altman"} == a.mention_docs


def test_resolver_keeps_longest_alias_as_display_name():
    r = Resolver()
    r.add("OpenAI", "Organization")
    e = r.add("OpenAI, Inc.", "Organization")
    assert e.name == "OpenAI, Inc."


def test_resolver_keeps_different_types_separate():
    r = Resolver()
    a = r.add("Attention", "Concept")
    b = r.add("Attention", "Method")
    assert a is not b
    assert a.id != b.id


def test_resolver_ignores_blank_names():
    r = Resolver()
    assert r.add("", "Person") is None
    assert r.add("   ", "Person") is None
    assert r.all() == []
