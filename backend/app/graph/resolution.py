"""Entity resolution: merge surface forms that refer to the same thing.

The LLM will spell entities inconsistently across (and within) articles —
"OpenAI" / "Open AI" / "OpenAI Inc." — and we don't want N nodes for one
concept. We canonicalize the name (lowercase, ASCII, alnum-only) and group
by ``(canonical_key, type)``. The display name we keep is the longest alias
we've seen, which empirically matches the most-formal version.

This is intentionally simple — no embedding similarity yet, no cross-type
collapsing. That's a fine starting point; we can layer fuzzy/embedding
merging in later if it matters for retrieval quality.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field


# Common organizational suffixes the LLM may or may not include; drop them
# so "OpenAI" and "OpenAI, Inc." resolve to the same entity.
_ORG_SUFFIXES = {"inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc", "co", "company"}


def normalize_name(name: str) -> str:
    """Canonicalize for matching: ASCII, lowercase, no punctuation, no spaces,
    no org suffixes. Aggressive on purpose — surface variations like
    ``OpenAI`` / ``Open AI`` / ``OpenAI, Inc.`` should all collapse to one key.
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9\s]+", " ", s).lower()
    tokens = [t for t in s.split() if t and t not in _ORG_SUFFIXES]
    return "".join(tokens)


def _entity_id(canonical_key: str, type_: str) -> str:
    return hashlib.sha1(f"{type_}::{canonical_key}".encode("utf-8")).hexdigest()[:16]


@dataclass
class CanonicalEntity:
    id: str
    name: str  # display form (longest alias seen)
    type: str
    aliases: set[str] = field(default_factory=set)
    mention_docs: set[str] = field(default_factory=set)


class Resolver:
    """Maintains the deduped set of entities and maps raw names to them."""

    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], CanonicalEntity] = {}

    def add(self, name: str, type_: str, source_doc: str | None = None) -> CanonicalEntity | None:
        name = (name or "").strip()
        if not name:
            return None
        key = normalize_name(name)
        if not key:
            return None
        dedup_key = (key, type_)
        entity = self._by_key.get(dedup_key)
        if entity is None:
            entity = CanonicalEntity(id=_entity_id(key, type_), name=name, type=type_)
            self._by_key[dedup_key] = entity
        entity.aliases.add(name)
        # Keep the most descriptive surface form as the display name.
        if len(name) > len(entity.name):
            entity.name = name
        if source_doc:
            entity.mention_docs.add(source_doc)
        return entity

    def all(self) -> list[CanonicalEntity]:
        return list(self._by_key.values())
