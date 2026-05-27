"""Tests for the recursive character chunker."""
from __future__ import annotations

import pytest

from app.ingestion.chunker import split_text


def test_empty_text_returns_no_chunks():
    assert split_text("") == []
    assert split_text("   \n  ") == []


def test_short_text_is_single_chunk():
    text = "A short sentence."
    assert split_text(text, chunk_size=800) == [text]


def test_chunks_respect_size_bound():
    text = ("word " * 1000).strip()  # ~5000 chars, no paragraph/sentence breaks
    chunks = split_text(text, chunk_size=200, chunk_overlap=20)
    assert len(chunks) > 1
    # allow a little slack for the strip()/overlap mechanics, but stay near bound
    assert all(len(c) <= 200 + 20 for c in chunks)


def test_overlap_carries_context_between_chunks():
    # Distinct word tokens so we can detect shared content across a boundary.
    text = " ".join(f"tok{i}" for i in range(300))
    chunks = split_text(text, chunk_size=120, chunk_overlap=40)
    assert len(chunks) >= 2
    # The tail of one chunk should reappear at the head of the next.
    tail = chunks[0][-20:]
    assert tail.split()[-1] in chunks[1]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("anything", chunk_size=100, chunk_overlap=100)


def test_full_text_is_covered():
    # Every non-overlapping word should survive somewhere in the output.
    text = "\n\n".join(f"Paragraph number {i} has some content." for i in range(50))
    chunks = split_text(text, chunk_size=150, chunk_overlap=30)
    joined = " ".join(chunks)
    for i in range(50):
        assert f"Paragraph number {i}" in joined
