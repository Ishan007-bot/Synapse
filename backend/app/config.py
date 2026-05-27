"""Application configuration, loaded from environment / .env file.

A single `settings` object is imported across the app so configuration lives in
one place. Values come from environment variables (see .env.example).
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = the directory that contains backend/ and .env
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider selection
    llm_provider: str = "groq"  # "groq" | "gemini"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "graphrag123"

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 120


settings = Settings()
