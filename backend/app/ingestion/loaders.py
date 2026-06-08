"""File-based document loaders.

Pairs with `wikipedia_loader.py` — both produce the same ``Document`` shape,
so the rest of the ingestion pipeline doesn't care where the text came from.

Each format has two entry points:
  * ``load_*`` from a filesystem ``Path`` (CLI flow)
  * ``load_*_bytes`` from already-buffered bytes (HTTP-upload flow)

Add a new format by writing two small functions and registering its extension
in ``SUPPORTED_EXTS``.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from .wikipedia_loader import Document

SUPPORTED_EXTS: frozenset[str] = frozenset({".txt", ".md", ".markdown", ".pdf"})


# ── plain text & markdown ────────────────────────────────────────────────


def load_text_file(path: Path) -> Document:
    text = path.read_text(encoding="utf-8", errors="replace")
    return Document(title=path.stem, url=f"file://{path.resolve()}", text=text)


def load_text_bytes(filename: str, data: bytes) -> Document:
    text = data.decode("utf-8", errors="replace")
    return Document(title=Path(filename).stem, url=f"upload://{filename}", text=text)


# ── PDF ──────────────────────────────────────────────────────────────────


def _pdf_to_text(reader) -> str:
    """Extract clean text from a pypdf reader. Page break = blank line."""
    pages = []
    for page in reader.pages:
        try:
            t = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — some PDFs raise on bad fonts; skip the page
            t = ""
        t = t.strip()
        if t:
            pages.append(t)
    return "\n\n".join(pages)


def load_pdf(path: Path) -> Document:
    # Imported lazily so the dep is only required if you actually load a PDF.
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return Document(title=path.stem, url=f"file://{path.resolve()}", text=_pdf_to_text(reader))


def load_pdf_bytes(filename: str, data: bytes) -> Document:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    return Document(title=Path(filename).stem, url=f"upload://{filename}", text=_pdf_to_text(reader))


# ── dispatch ─────────────────────────────────────────────────────────────


def load_file(path: Path) -> Document | None:
    """Load a file by extension. Returns None for unsupported types."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf(path)
    if ext in {".txt", ".md", ".markdown"}:
        return load_text_file(path)
    return None


def load_bytes(filename: str, data: bytes) -> Document | None:
    """Same as load_file, but for an already-buffered upload."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return load_pdf_bytes(filename, data)
    if ext in {".txt", ".md", ".markdown"}:
        return load_text_bytes(filename, data)
    return None


def load_folder(folder: Path, exts: frozenset[str] | None = None) -> list[Document]:
    """Load every supported file in `folder` (non-recursive)."""
    exts = exts or SUPPORTED_EXTS
    out: list[Document] = []
    for p in sorted(folder.iterdir()):
        if not p.is_file() or p.suffix.lower() not in exts:
            continue
        doc = load_file(p)
        if doc and doc.text.strip():
            out.append(doc)
    return out
