"""Build the configured LLM provider.

Call `get_provider()` to get whatever is set in LLM_PROVIDER, or
`get_provider("gemini")` to force a specific one.
"""
from __future__ import annotations

from ..config import settings
from .base import LLMProvider


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or settings.llm_provider).lower()

    if name == "groq":
        from .groq_provider import GroqProvider

        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)

    if name == "gemini":
        from .gemini_provider import GeminiProvider

        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    raise ValueError(f"Unknown LLM provider: {name!r}. Use 'groq' or 'gemini'.")
