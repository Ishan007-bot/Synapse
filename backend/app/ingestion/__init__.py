"""Ingestion: fetch source documents, chunk them, and write them into Neo4j."""
from .chunker import split_text
from .corpus import CORPUS
from .wikipedia_loader import Document, fetch_article, fetch_corpus

__all__ = ["split_text", "CORPUS", "Document", "fetch_article", "fetch_corpus"]
