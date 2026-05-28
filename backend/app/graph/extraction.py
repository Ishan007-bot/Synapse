"""LLM-based entity and relation extraction.

For each document we split the text into ~15K-char windows and extract from
each window in turn, then merge the results. This is what production
extraction pipelines do and keeps every LLM call well inside any free-tier
per-call budget (Groq's 12K TPM, Gemini's per-request limits). We also retry
on rate-limit errors with a short back-off so a transient 429 doesn't kill a
build.

We extract at the document level (not per chunk) so the LLM has global
context about who/what is being discussed. The :Entity -> :Chunk linkage is
recovered afterwards by text containment (see ``store.link_mentions``).

The prompt forces a strict JSON shape and providers run in JSON mode so the
output is reliably parseable. On a JSON/validation failure we retry once with
a self-correcting hint.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import TYPE_CHECKING

from pydantic import ValidationError

from ..llm import Message, get_provider
from .schema import ENTITY_TYPES, Entity, ExtractionResult, Relation

if TYPE_CHECKING:
    from ..llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Suggested relation labels — the validator normalizes anything to UPPER_SNAKE_CASE.
_RELATION_HINTS = (
    "FOUNDED, CO_FOUNDED, WORKS_AT, WORKED_AT, ADVISED, COLLABORATED_WITH, "
    "CREATED, INTRODUCED, USES, PART_OF, ACQUIRED, ACQUIRED_BY, "
    "RECEIVED_AWARD, BORN_IN, BASED_IN, AFFILIATED_WITH, INFLUENCED_BY"
)

SYSTEM_PROMPT = (
    "You are an information extraction engine building a knowledge graph about "
    "the field of artificial intelligence. From the article excerpt you are "
    "given, extract the salient entities and the relations between them.\n\n"
    "Return a single JSON object with exactly two keys: \"entities\" and "
    "\"relations\".\n"
    "- Each entity has a \"name\" (the canonical form as it appears in the text) "
    f"and a \"type\" which MUST be one of: {', '.join(ENTITY_TYPES)}.\n"
    "- Each relation has \"source\" (entity name), \"target\" (entity name), and "
    "\"type\" (UPPER_SNAKE_CASE verb phrase, e.g. " + _RELATION_HINTS + ").\n"
    "- Every relation's source and target MUST appear in the entities array.\n"
    "- Prefer specific entities (people, organizations, named models, named "
    "methods, awards, places) over generic ones; ignore boilerplate (citations, "
    "navigation, see-also lists).\n"
    "- Do not invent facts not stated in the text.\n"
    "Output ONLY the JSON object, no prose, no markdown fences."
)


def _build_messages(title: str, text: str) -> list[Message]:
    user = (
        f"Article: {title}\n\n"
        f"Text:\n{text}\n\n"
        "Extract the entities and relations now. Return JSON only."
    )
    return [Message("system", SYSTEM_PROMPT), Message("user", user)]


def _validate(payload: dict) -> ExtractionResult:
    result = ExtractionResult.model_validate(payload)
    # Drop relations whose endpoints aren't in the entity list — keeps the graph consistent.
    names = {e.name for e in result.entities}
    result.relations = [r for r in result.relations if r.source in names and r.target in names]
    return result


_RATE_LIMIT_HINTS = ("rate_limit", "rate limit", "429", "tpm", "rpm", "quota", "exhausted", "exceeded")


def _is_rate_limit(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(h in msg for h in _RATE_LIMIT_HINTS)


def _retry_after_seconds(exc: Exception, default: float) -> float:
    """Best-effort parse of "try again in 24s" / "retryDelay: 24s" from provider errors."""
    msg = str(exc)
    for pat in (r"try again in (\d+(?:\.\d+)?)\s*s", r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)\s*s"):
        m = re.search(pat, msg)
        if m:
            return float(m.group(1))
    return default


def _split_into_windows(text: str, max_chars: int) -> list[str]:
    """Split text into windows ≤ max_chars, snapping to paragraph/line breaks when possible."""
    if len(text) <= max_chars:
        return [text]
    windows: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # Prefer a paragraph break, then a line break, in the back half of the window.
            for sep in ("\n\n", "\n", ". "):
                cut = text.rfind(sep, start + max_chars // 2, end)
                if cut != -1:
                    end = cut + len(sep)
                    break
        windows.append(text[start:end])
        start = end
    return windows


def _call_llm(
    title: str,
    text: str,
    provider: "LLMProvider",
    *,
    max_tokens: int,
    max_attempts: int = 4,
) -> ExtractionResult:
    """Call the LLM with rate-limit-aware retries and a JSON-validation retry."""
    messages = _build_messages(title, text)

    for attempt in range(max_attempts):
        try:
            payload = provider.generate_json(messages, temperature=0.0, max_tokens=max_tokens)
            try:
                return _validate(payload)
            except (ValidationError, ValueError, KeyError) as exc:
                logger.warning("extraction validation failed (%s); asking for correction", exc)
                messages = messages + [
                    Message(
                        "user",
                        "Your previous response did not match the schema. Return ONLY a JSON "
                        "object with keys 'entities' and 'relations'. Each entity needs "
                        "'name' and 'type'; each relation needs 'source', 'target', 'type'.",
                    )
                ]
                continue
        except json.JSONDecodeError as exc:
            logger.warning("JSON decode failed (%s); retrying", exc)
            continue
        except Exception as exc:
            if _is_rate_limit(exc) and attempt < max_attempts - 1:
                wait = _retry_after_seconds(exc, default=5.0 * (attempt + 1))
                logger.warning("rate-limited; sleeping %.1fs (attempt %d/%d)", wait, attempt + 1, max_attempts)
                time.sleep(wait + 1)
                continue
            logger.error("extraction failed for %r: %s", title, exc)
            return ExtractionResult()

    logger.error("extraction exhausted retries for %r", title)
    return ExtractionResult()


def _merge(results: list[ExtractionResult]) -> ExtractionResult:
    """Merge per-window results, de-duplicating entities by (name, type)."""
    by_key: dict[tuple[str, str], Entity] = {}
    relations: list[Relation] = []
    for r in results:
        for e in r.entities:
            by_key.setdefault((e.name, e.type), e)
        relations.extend(r.relations)
    return ExtractionResult(entities=list(by_key.values()), relations=relations)


def extract_from_document(
    title: str,
    text: str,
    provider: "LLMProvider | None" = None,
    *,
    max_tokens: int = 4096,
    max_chars_per_window: int = 12_000,
) -> ExtractionResult:
    """Extract entities and relations from a full document."""
    provider = provider or get_provider()
    windows = _split_into_windows(text, max_chars_per_window)
    if len(windows) == 1:
        return _call_llm(title, windows[0], provider, max_tokens=max_tokens)

    logger.info("extracting %r in %d windows", title, len(windows))
    results: list[ExtractionResult] = []
    for i, window in enumerate(windows, start=1):
        sub_title = f"{title} (part {i}/{len(windows)})"
        results.append(_call_llm(sub_title, window, provider, max_tokens=max_tokens))
    return _merge(results)
