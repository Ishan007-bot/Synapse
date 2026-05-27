"""Fetch Wikipedia articles as plain-text Documents.

Uses the `wikipedia-api` package, which returns clean article text (no markup),
which is what we want to feed the chunker and, later, the entity extractor.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import wikipediaapi

# Wikipedia asks API clients to identify themselves with a descriptive UA.
_USER_AGENT = "Synapse-GraphRAG/0.1 (educational portfolio project)"


@dataclass
class Document:
    """A source document ready to be chunked and stored."""

    title: str
    url: str
    text: str


def _client(lang: str = "en") -> wikipediaapi.Wikipedia:
    return wikipediaapi.Wikipedia(user_agent=_USER_AGENT, language=lang)


def fetch_article(title: str, lang: str = "en") -> Document | None:
    """Fetch a single article. Returns None if the page does not exist."""
    page = _client(lang).page(title)
    if not page.exists():
        return None
    return Document(title=page.title, url=page.fullurl, text=page.text)


def fetch_corpus(titles: Iterable[str], lang: str = "en") -> tuple[list[Document], list[str]]:
    """Fetch many articles.

    Returns (documents, missing_titles) so the caller can report any titles that
    didn't resolve to a real page.
    """
    docs: list[Document] = []
    missing: list[str] = []
    wiki = _client(lang)
    for title in titles:
        page = wiki.page(title)
        if page.exists():
            docs.append(Document(title=page.title, url=page.fullurl, text=page.text))
        else:
            missing.append(title)
    return docs, missing
