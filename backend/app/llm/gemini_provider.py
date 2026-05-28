"""Gemini provider — Google's free-tier models via the google-genai SDK.

Gemini's API differs from the OpenAI/Groq schema: the system prompt is passed
separately and conversation turns use roles "user" / "model". We translate our
provider-agnostic `Message` list into that shape here.
"""
from __future__ import annotations

import json
from typing import Iterator

from google import genai
from google.genai import types

from .base import LLMProvider, Message


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")
        self._client = genai.Client(api_key=api_key)
        self._model = model

    @staticmethod
    def _split(messages: list[Message]) -> tuple[str | None, list[types.Content]]:
        """Separate the system instruction from the user/model conversation turns."""
        system_parts = [m.content for m in messages if m.role == "system"]
        system = "\n".join(system_parts) or None

        contents: list[types.Content] = []
        for m in messages:
            if m.role == "system":
                continue
            role = "model" if m.role == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=m.content)]))
        return system, contents

    def generate(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        system, contents = self._split(messages)
        resp = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        return resp.text or ""

    def stream(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        system, contents = self._split(messages)
        stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    def generate_json(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> dict:
        system, contents = self._split(messages)
        # Disable "thinking" for 2.5+ models — the silent reasoning phase makes
        # each call 10-30s slower with no quality gain for structured extraction.
        # Older Gemini versions ignore the field, so it's safe to always pass.
        thinking_config = None
        if hasattr(types, "ThinkingConfig"):
            try:
                thinking_config = types.ThinkingConfig(thinking_budget=0)
            except TypeError:
                thinking_config = None
        resp = self._client.models.generate_content(
            model=self._model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                thinking_config=thinking_config,
            ),
        )
        return json.loads(resp.text or "{}")
