"""Deterministic prerequisite gap detection (spec §15)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Concept
from app.db.repositories import KnowledgeRepository
from app.knowledge.graph import KnowledgeGraph
from app.learning.mastery import MasteryService

MASTERED = "MASTERED"
WEAK = "WEAK"
UNKNOWN = "UNKNOWN"

# Priority for ranking gaps: ungrounded/untested prerequisites come first,
# then weak ones ordered by lowest mastery.
_SEVERITY = {UNKNOWN: 0, WEAK: 1}


@dataclass(frozen=True)
class GapEntry:
    concept: Concept
    distance: int
    status: str
    mastery: float | None
    evidence_count: int
    has_source_evidence: bool


@dataclass(frozen=True)
class GapReport:
    target: Concept
    prerequisites: list[GapEntry]
    gaps: list[GapEntry]  # non-mastered prerequisites, ranked for teaching order


class GapDetector:
    def __init__(
        self,
        session: Session,
        *,
        mastered_threshold: float = 0.80,
        weak_threshold: float = 0.40,
        min_evidence: int = 3,
    ) -> None:
        self.repository = KnowledgeRepository(session)
        self.mastery = MasteryService(session)
        self.graph = KnowledgeGraph(self.repository)
        self.mastered_threshold = mastered_threshold
        self.weak_threshold = weak_threshold
        self.min_evidence = min_evidence

    def detect(self, target_concept_id: int) -> GapReport:
        target = self.repository.get_concept(target_concept_id)
        if target is None:
            raise ValueError(f"Concept {target_concept_id} not found.")

        entries: list[GapEntry] = []
        for concept_id, distance in self.graph.prerequisites(target_concept_id):
            concept = self.repository.get_concept(concept_id)
            if concept is None:  # dangling edge; ignore rather than crash
                continue
            record = self.mastery.get_record(concept_id)
            estimate = self.mastery.get_estimate(concept_id)
            evidence_count = record.evidence_count if record else 0
            entries.append(
                GapEntry(
                    concept=concept,
                    distance=distance,
                    status=self.classify(estimate, evidence_count),
                    mastery=estimate,
                    evidence_count=evidence_count,
                    has_source_evidence=bool(concept.source_chunks),
                )
            )

        gaps = [entry for entry in entries if entry.status != MASTERED]
        gaps.sort(key=lambda entry: (entry.distance, _SEVERITY[entry.status], entry.mastery or 0.0))
        return GapReport(target=target, prerequisites=entries, gaps=gaps)

    def classify(self, estimate: float | None, evidence_count: int) -> str:
        if estimate is None or evidence_count < self.min_evidence:
            return UNKNOWN
        if estimate >= self.mastered_threshold:
            return MASTERED
        if estimate >= self.weak_threshold:
            return WEAK
        return UNKNOWN
