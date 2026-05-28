"""Disk cache for extraction results.

Calling the LLM 27 times to rebuild the same graph is wasteful (and burns the
free tier). We cache each document's extraction as JSON keyed by article
title; re-runs skip the LLM unless ``--no-cache`` is passed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .schema import ExtractionResult

# project_root/data/cache/extractions/
_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache" / "extractions"


def _slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("_") or "untitled"


def _path(title: str) -> Path:
    return _CACHE_DIR / f"{_slug(title)}.json"


def get(title: str) -> ExtractionResult | None:
    path = _path(title)
    if not path.exists():
        return None
    try:
        return ExtractionResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001 - corrupted cache shouldn't crash a build
        return None


def put(title: str, result: ExtractionResult) -> None:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _path(title).write_text(result.model_dump_json(indent=2), encoding="utf-8")
