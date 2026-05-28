"""Knowledge graph construction: extract entities & relations from documents,
resolve duplicates, and write the resulting graph into Neo4j."""
from .resolution import Resolver, normalize_name
from .schema import ENTITY_TYPES, Entity, ExtractionResult, Relation

__all__ = [
    "ENTITY_TYPES",
    "Entity",
    "ExtractionResult",
    "Relation",
    "Resolver",
    "normalize_name",
]
