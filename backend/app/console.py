"""Console helpers.

Windows terminals default to cp1252, which can't encode characters common in
Wikipedia text (smart quotes, em-dashes, accents). CLI entry points call
`enable_utf8()` so printing never crashes with UnicodeEncodeError.
"""
from __future__ import annotations

import sys


def enable_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
