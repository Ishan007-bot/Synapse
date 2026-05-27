"""A recursive character text splitter, implemented from scratch.

The idea (same as LangChain's RecursiveCharacterTextSplitter, but transparent):

1. Break the text into small "atoms" using a hierarchy of separators — paragraph
   breaks first, then lines, then sentences, then words, then characters. We stop
   descending as soon as an atom fits within `chunk_size`.
2. Greedily pack consecutive atoms into chunks up to `chunk_size`, carrying a tail
   of `chunk_overlap` characters from each chunk into the next so context isn't
   lost at boundaries (important for retrieval quality).
"""
from __future__ import annotations

# Tried in order: paragraphs -> lines -> sentences -> words -> characters.
DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _recursive_split(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    """Split `text` into pieces, each (best-effort) no longer than `chunk_size`."""
    if len(text) <= chunk_size:
        return [text] if text else []

    # No separators left, or the empty separator: hard-split by character.
    if not separators or separators[0] == "":
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    sep, rest = separators[0], separators[1:]
    pieces: list[str] = []
    for part in text.split(sep):
        if not part:
            continue
        segment = part + sep  # keep the separator so chunks read naturally
        if len(segment) <= chunk_size:
            pieces.append(segment)
        else:
            pieces.extend(_recursive_split(segment, chunk_size, rest))
    return pieces


def _merge_with_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    """Pack atoms into chunks up to `chunk_size`, overlapping by `chunk_overlap` chars."""
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current.strip())
            # seed the next chunk with the tail of this one for continuity
            current = current[-chunk_overlap:] if chunk_overlap > 0 else ""
        current += piece
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def split_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    separators: list[str] | None = None,
) -> list[str]:
    """Split `text` into overlapping chunks suitable for embedding."""
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    text = text.strip()
    if not text:
        return []
    atoms = _recursive_split(text, chunk_size, separators or DEFAULT_SEPARATORS)
    return _merge_with_overlap(atoms, chunk_size, chunk_overlap)
