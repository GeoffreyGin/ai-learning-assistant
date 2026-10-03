"""Deterministic next-topic recommendation (spec §13, §14 step 10)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Concept
from app.db.repositories import KnowledgeRepository
from app.learning.gap_detector import MASTERED, UNKNOWN, WEAK, GapDetector, GapEntry
from app.learning.mastery import MasteryService

_SEVERITY = {UNKNOWN: 0, WEAK: 1}


@dataclass(frozen=True)
class RecommendedTopic:
    concept: Concept
    status: str
    mastery: float | None
    evidence_count: int
    reason: str


class Recommender:
    def __init__(self, session: Session, gap_detector: GapDetector) -> None:
        self.repository = KnowledgeRepository(session)
        self.mastery = MasteryService(session)
        self.gap_detector = gap_detector

    def recommend(
        self, target_concept_id: int | None = None, limit: int = 3
    ) -> list[RecommendedTopic]:
        if target_concept_id is not None:
            report = self.gap_detector.detect(target_concept_id)
            topics = [self._from_gap(entry) for entry in report.gaps[:limit]]
            if not topics:
                record = self.mastery.get_record(report.target.id)
                topics = [
                    RecommendedTopic(
                        concept=report.target,
                        status=MASTERED,
                        mastery=self.mastery.get_estimate(report.target.id),
                        evidence_count=record.evidence_count if record else 0,
                        reason=(
                            f"All known prerequisites of '{report.target.name}' look "
                            "mastered; assess the target itself."
                        ),
                    )
                ]
            return topics
        return self._global_scan(limit)

    def _global_scan(self, limit: int) -> list[RecommendedTopic]:
        ranked: list[tuple[tuple, RecommendedTopic]] = []
        for concept in self.repository.list_concepts():
            record = self.mastery.get_record(concept.id)
            estimate = self.mastery.get_estimate(concept.id)
            evidence = record.evidence_count if record else 0
            status = self.gap_detector.classify(estimate, evidence)
            if status == MASTERED:
                continue
            topic = RecommendedTopic(
                concept=concept,
                status=status,
                mastery=estimate,
                evidence_count=evidence,
                reason=self._reason(status, estimate, evidence),
            )
            ranked.append(((_SEVERITY[status], evidence, estimate or 0.0, concept.id), topic))
        ranked.sort(key=lambda item: item[0])
        return [topic for _, topic in ranked[:limit]]

    def _from_gap(self, entry: GapEntry) -> RecommendedTopic:
        return RecommendedTopic(
            concept=entry.concept,
            status=entry.status,
            mastery=entry.mastery,
            evidence_count=entry.evidence_count,
            reason=self._reason(entry.status, entry.mastery, entry.evidence_count),
        )

    @staticmethod
    def _reason(status: str, mastery: float | None, evidence_count: int) -> str:
        if status == UNKNOWN:
            if evidence_count == 0:
                return "No mastery evidence yet."
            return f"Not enough evidence ({evidence_count} assessment(s))."
        return f"Weak: estimated mastery {mastery:.0%} after {evidence_count} assessment(s)."
