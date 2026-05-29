"""LLM judge used by every metric.

A small JSON-mode wrapper around our LLM provider with disk caching keyed by
prompt content. RAG evaluation needs many small judgments per question
(hundreds across a full run); caching means the second run is free and lets
us iterate on metrics without burning free-tier quota.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from ..llm import LLMProvider, Message, get_provider

logger = logging.getLogger(__name__)

# project_root/data/eval/judge_cache/<hash>.json
_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "eval" / "judge_cache"

_RATE_LIMIT_HINTS = ("rate_limit", "rate limit", "429", "tpm", "rpm", "quota", "exceeded")
# Anything network-flavoured we'd also like to retry instead of dying mid-eval.
_TRANSIENT_HINTS = ("timeout", "timed out", "connection error", "connection reset", "temporarily")


class Judge:
    """Thin LLM client tuned for short, deterministic, JSON-mode judgments."""

    def __init__(self, provider: LLMProvider | None = None, *, model_hint: str = "") -> None:
        self.provider = provider or get_provider()
        self.model_hint = model_hint or self.provider.name

    # ── caching ──────────────────────────────────────────────────────────

    def _key(self, system: str, user: str) -> Path:
        h = hashlib.sha1(f"{self.model_hint}\n---\n{system}\n---\n{user}".encode("utf-8")).hexdigest()
        return _CACHE_DIR / f"{h[:16]}.json"

    def _read_cache(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, path: Path, value: Any) -> None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    # ── core call with rate-limit retry ──────────────────────────────────

    def _call(self, system: str, user: str, *, max_tokens: int = 800, retries: int = 4) -> dict:
        cache_path = self._key(system, user)
        cached = self._read_cache(cache_path)
        if cached is not None:
            return cached

        messages = [Message("system", system), Message("user", user)]
        delay = 5.0
        for attempt in range(retries):
            try:
                payload = self.provider.generate_json(messages, temperature=0.0, max_tokens=max_tokens)
                self._write_cache(cache_path, payload)
                return payload
            except json.JSONDecodeError as e:
                logger.warning("judge JSON parse failed (%s); retrying", e)
                continue
            except Exception as e:
                msg = str(e).lower()
                cls = type(e).__name__.lower()
                is_rate = any(h in msg for h in _RATE_LIMIT_HINTS)
                is_transient = any(h in msg or h in cls for h in _TRANSIENT_HINTS)
                if (is_rate or is_transient) and attempt < retries - 1:
                    wait = _parse_retry_after(str(e), default=delay) if is_rate else delay
                    kind = "rate-limited" if is_rate else "transient network"
                    logger.warning("judge %s; sleeping %.1fs (attempt %d)", kind, wait, attempt + 1)
                    time.sleep(wait + 1)
                    delay = min(delay * 2, 60.0)
                    continue
                raise
        return {}

    # ── prompts ──────────────────────────────────────────────────────────

    def extract_claims(self, answer: str) -> list[str]:
        """Break a generated answer into atomic factual claims."""
        if not answer.strip():
            return []
        system = (
            "Split the given assistant ANSWER into atomic, self-contained factual claims. "
            "Each claim should make sense on its own. Drop hedges, disclaimers, refusals, "
            "and citations like '[Source]'. Return JSON: {\"claims\": [\"...\"]}."
        )
        payload = self._call(system, f"ANSWER:\n{answer}")
        claims = payload.get("claims", []) if isinstance(payload, dict) else []
        return [c.strip() for c in claims if isinstance(c, str) and c.strip()]

    def claim_supported(self, claim: str, context: str) -> bool:
        """Is this claim supported by the context?"""
        system = (
            "Decide whether the CLAIM is supported by the CONTEXT. Be strict: a claim is "
            "supported only if every fact it states can be inferred from the context. "
            "Return JSON: {\"supported\": true|false}."
        )
        payload = self._call(system, f"CONTEXT:\n{context}\n\nCLAIM:\n{claim}", max_tokens=300)
        return bool(payload.get("supported", False))

    def context_relevant(self, question: str, context: str) -> bool:
        """Is this context piece relevant to answering the question?"""
        system = (
            "Decide whether the CONTEXT could help answer the QUESTION. Even partial "
            "relevance counts. Return JSON: {\"relevant\": true|false}."
        )
        payload = self._call(system, f"QUESTION:\n{question}\n\nCONTEXT:\n{context}", max_tokens=300)
        return bool(payload.get("relevant", False))

    def extract_reference_facts(self, reference: str) -> list[str]:
        """Atomic facts in the reference answer (for context recall)."""
        if not reference.strip():
            return []
        system = (
            "Split the REFERENCE answer into atomic factual statements. Each should make "
            "sense on its own. Return JSON: {\"facts\": [\"...\"]}."
        )
        payload = self._call(system, f"REFERENCE:\n{reference}")
        facts = payload.get("facts", []) if isinstance(payload, dict) else []
        return [f.strip() for f in facts if isinstance(f, str) and f.strip()]

    def fact_covered(self, fact: str, context: str) -> bool:
        """Is this reference fact present in (or inferable from) the retrieved context?"""
        system = (
            "Decide whether the FACT can be inferred from the CONTEXT. Be reasonable: "
            "paraphrases and equivalent statements count as covered. Return JSON: "
            "{\"covered\": true|false}."
        )
        payload = self._call(system, f"CONTEXT:\n{context}\n\nFACT:\n{fact}", max_tokens=300)
        return bool(payload.get("covered", False))

    def generate_questions_for(self, answer: str, n: int = 3) -> list[str]:
        """Generate plausible questions that would lead to this answer.

        Used by the answer-relevancy metric: an answer that's well-aligned with
        the original question should yield generated questions semantically
        close to the original.
        """
        if not answer.strip():
            return []
        system = (
            f"Given the ANSWER below, write {n} different questions that a user might ask "
            "to receive this exact answer. Be concise. Return JSON: {\"questions\": [\"...\"]}."
        )
        payload = self._call(system, f"ANSWER:\n{answer}", max_tokens=400)
        qs = payload.get("questions", []) if isinstance(payload, dict) else []
        return [q.strip() for q in qs if isinstance(q, str) and q.strip()][:n]


def _parse_retry_after(msg: str, default: float) -> float:
    for pat in (r"try again in (\d+(?:\.\d+)?)\s*s", r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)\s*s"):
        m = re.search(pat, msg)
        if m:
            return float(m.group(1))
    return default
