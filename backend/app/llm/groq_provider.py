"""Groq provider — fast inference of open models (Llama 3.3 70B by default)."""
from __future__ import annotations

from typing import Iterator

from groq import Groq

from .base import LLMProvider, Message


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set. Add it to your .env file.")
        self._client = Groq(api_key=api_key)
        self._model = model

    @staticmethod
    def _to_payload(messages: list[Message]) -> list[dict]:
        # Groq follows the OpenAI chat schema, so the mapping is 1:1.
        return [{"role": m.role, "content": m.content} for m in messages]

    def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=self._to_payload(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=self._to_payload(messages),
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
