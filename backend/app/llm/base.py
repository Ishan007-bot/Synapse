"""The provider-agnostic LLM interface.

Every concrete provider (Groq, Gemini, ...) implements `generate` (blocking,
returns the full string) and `stream` (yields text deltas). Callers build a list
of `Message` objects and never import a vendor SDK directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Literal

Role = Literal["system", "user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str


class LLMProvider(ABC):
    """Common interface implemented by every LLM backend."""

    #: short identifier, e.g. "groq" / "gemini"
    name: str

    @abstractmethod
    def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        """Return the model's full response as a string."""

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Yield response text incrementally (token/chunk deltas)."""

    @abstractmethod
    def generate_json(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict:
        """Force the model to return a JSON object and parse it.

        Used for structured extraction (Phase 3 entity/relation extraction).
        Implementations should use the provider's native JSON-mode (Groq
        ``response_format={"type": "json_object"}``, Gemini
        ``response_mime_type="application/json"``) so the output is reliably
        parseable.
        """
