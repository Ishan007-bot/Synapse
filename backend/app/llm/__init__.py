"""LLM provider abstraction.

The rest of the app talks only to the `LLMProvider` interface, so we can swap
Groq <-> Gemini (or add others) without touching call sites.
"""
from .base import LLMProvider, Message
from .factory import get_provider

__all__ = ["LLMProvider", "Message", "get_provider"]
