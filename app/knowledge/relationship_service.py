"""Shared write-path for relationships referenced by concept names."""

from __future__ import annotations

from app.db.models import Concept
from app.db.repositories import KnowledgeRepository, normalize_concept_name
from app.knowledge.relations import RELATION_TYPES
from app.knowledge.resolver import ConceptResolver


class RelationshipService:
    def __init__(self, repository: KnowledgeRepository, resolver: ConceptResolver) -> None:
        self.repository = repository
        self.resolver = resolver

    def resolve_or_create(self, name: str) -> Concept:
        normalized = normalize_concept_name(name)
        if not normalized:
            raise ValueError("Concept name must contain letters or numbers.")
        existing = self.repository.get_concept_by_normalized(normalized)
        if existing is not None:
            return existing
        concept, _ = self.resolver.resolve(name)
        return concept

    def create(
        self,
        *,
        source: str,
        target: str,
        relation_type: str,
        confidence: float = 0.7,
        evidence_source_id: int | None = None,
    ) -> dict:
        relation_type = relation_type.strip().upper()
        if relation_type not in RELATION_TYPES:
            allowed = ", ".join(sorted(RELATION_TYPES))
            raise ValueError(
                f"Unsupported relationship type {relation_type!r}. Use one of: {allowed}."
            )
        source_concept = self.resolve_or_create(source)
        target_concept = self.resolve_or_create(target)
        relationship, created = self.repository.create_relationship(
            source_concept_id=source_concept.id,
            target_concept_id=target_concept.id,
            relation_type=relation_type,
            confidence=min(1.0, max(0.0, confidence)),
            evidence_source_id=evidence_source_id,
        )
        return {
            "id": relationship.id,
            "source_concept_id": source_concept.id,
            "target_concept_id": target_concept.id,
            "relation_type": relation_type,
            "confidence": relationship.confidence,
            "created": created,
        }
