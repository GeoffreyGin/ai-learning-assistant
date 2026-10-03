from __future__ import annotations

import re
from typing import Protocol

from pydantic import BaseModel, Field, field_validator


class ExtractedConcept(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2_000)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Concept name cannot be blank.")
        return cleaned


class ExtractedRelationship(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    type: str
    confidence: float = Field(ge=0, le=1)


class ExtractionResult(BaseModel):
    concepts: list[ExtractedConcept] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)


class ConceptExtractor(Protocol):
    def extract(self, text: str) -> ExtractionResult: ...


class LocalConceptExtractor:
    """Deterministic fallback for offline use and tests; an LLM provider can replace it later."""

    heading_pattern = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
    proper_phrase_pattern = re.compile(r"\b(?:[A-Z][\w'’.-]*)(?:[ \t]+(?:[A-Z][\w'’.-]*)){1,4}\b")

    def extract(self, text: str) -> ExtractionResult:
        candidates = self.heading_pattern.findall(text) + self.proper_phrase_pattern.findall(text)
        seen: set[str] = set()
        concepts: list[ExtractedConcept] = []
        for candidate in candidates:
            clean = re.sub(r"\s+", " ", candidate).strip(" .:-")
            key = re.sub(r"[^a-z0-9]+", "", clean.casefold())
            if len(clean) < 3 or key in seen:
                continue
            seen.add(key)
            concepts.append(ExtractedConcept(name=clean, description=f"Mentioned in uploaded material: {clean}."))
        return ExtractionResult(concepts=concepts[:30])
