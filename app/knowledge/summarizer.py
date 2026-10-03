from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from app.db.models import Concept, Document, SourceChunk


@dataclass(frozen=True)
class GroundedClaim:
    text: str
    source_chunk_id: int


@dataclass(frozen=True)
class KnowledgeSummary:
    overview: str
    key_concepts: list[str]
    claims: list[GroundedClaim]


class LocalKnowledgeSummarizer:
    """A transparent, extractive baseline that only returns text from the source material.

    A future LLM-backed summarizer can implement this same output shape, while this
    version keeps the MVP useful without API credentials or unsupported claims.
    """

    sentence_pattern = re.compile(r"(?<=[.!?])\s+|\n+")

    def summarize(self, document: Document, concepts: list[Concept]) -> KnowledgeSummary:
        chunks = document.chunks
        if not chunks:
            return KnowledgeSummary("No readable source text is available.", [], [])

        concept_counts = Counter()
        for concept in concepts:
            occurrences = sum(chunk.text.casefold().count(concept.name.casefold()) for chunk in chunks)
            concept_counts[concept.name] = max(occurrences, 1)
        key_concepts = [name for name, _ in concept_counts.most_common(5)]

        candidates: list[tuple[int, int, str]] = []
        keywords = [word.casefold() for name in key_concepts for word in re.findall(r"[\w]+", name)]
        for chunk in chunks:
            for sentence in self.sentence_pattern.split(chunk.text):
                clean = re.sub(r"\s+", " ", sentence).strip()
                if len(clean) < 25:
                    continue
                score = sum(clean.casefold().count(keyword) for keyword in keywords)
                candidates.append((score, chunk.id, clean))
        if not candidates:
            candidates = [(0, chunks[0].id, chunks[0].text.strip())]

        selected = sorted(candidates, key=lambda item: (-item[0], item[1]))[:3]
        claims = [GroundedClaim(text=text, source_chunk_id=chunk_id) for _, chunk_id, text in selected]
        overview = " ".join(claim.text for claim in claims)
        return KnowledgeSummary(overview=overview, key_concepts=key_concepts, claims=claims)
