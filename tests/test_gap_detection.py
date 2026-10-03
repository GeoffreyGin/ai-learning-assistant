"""Gap detection tests (spec §15, §26)."""

from datetime import UTC, datetime

import pytest

from app.db.repositories import KnowledgeRepository
from app.learning.gap_detector import MASTERED, UNKNOWN, WEAK, GapDetector


def seed_mastery(session, concept, mastery: float, evidence: int) -> None:
    repository = KnowledgeRepository(session)
    repository.upsert_mastery_record(
        concept_id=concept.id,
        estimated_mastery=mastery,
        evidence_count=evidence,
        correct_count=max(0, evidence - 1),
        incorrect_count=1 if mastery < 0.8 else 0,
        last_tested_at=datetime.now(UTC),
    )
    session.commit()


def test_missing_prerequisite_detected(session_factory, seed) -> None:
    concepts = seed(["Calculus", "Black-Scholes"], edges=[("Calculus", "Black-Scholes")])
    with session_factory() as session:
        report = GapDetector(session, min_evidence=1).detect(concepts["Black-Scholes"].id)
        assert len(report.prerequisites) == 1
        assert report.gaps[0].concept.name == "Calculus"
        assert report.gaps[0].status == UNKNOWN
        assert report.gaps[0].mastery is None


def test_weak_prerequisite_detected(session_factory, seed) -> None:
    concepts = seed(["Calculus", "Black-Scholes"], edges=[("Calculus", "Black-Scholes")])
    with session_factory() as session:
        seed_mastery(session, concepts["Calculus"], mastery=0.5, evidence=5)
        report = GapDetector(session, min_evidence=1).detect(concepts["Black-Scholes"].id)
        assert report.gaps[0].status == WEAK


def test_mastered_prerequisite_ignored(session_factory, seed) -> None:
    concepts = seed(["Calculus", "Black-Scholes"], edges=[("Calculus", "Black-Scholes")])
    with session_factory() as session:
        seed_mastery(session, concepts["Calculus"], mastery=0.9, evidence=5)
        report = GapDetector(session, min_evidence=1).detect(concepts["Black-Scholes"].id)
        assert report.prerequisites[0].status == MASTERED
        assert report.gaps == []


def test_insufficient_evidence_is_unknown(session_factory, seed) -> None:
    concepts = seed(["Calculus", "Black-Scholes"], edges=[("Calculus", "Black-Scholes")])
    with session_factory() as session:
        seed_mastery(session, concepts["Calculus"], mastery=0.95, evidence=1)
        report = GapDetector(session, min_evidence=3).detect(concepts["Black-Scholes"].id)
        assert report.prerequisites[0].status == UNKNOWN


def test_thresholds_are_configurable(session_factory, seed) -> None:
    concepts = seed(["Calculus", "Black-Scholes"], edges=[("Calculus", "Black-Scholes")])
    with session_factory() as session:
        seed_mastery(session, concepts["Calculus"], mastery=0.9, evidence=5)
        detector = GapDetector(session, mastered_threshold=0.95, weak_threshold=0.4, min_evidence=1)
        assert detector.detect(concepts["Black-Scholes"].id).prerequisites[0].status == WEAK


def test_gaps_ranked_by_distance_and_severity(session_factory, seed) -> None:
    concepts = seed(
        ["A", "B", "C", "Target"],
        edges=[("A", "B"), ("B", "Target"), ("C", "Target")],
    )
    with session_factory() as session:
        seed_mastery(session, concepts["C"], mastery=0.5, evidence=5)  # WEAK at distance 1
        report = GapDetector(session, min_evidence=1).detect(concepts["Target"].id)
        # B (UNKNOWN, distance 1) beats C (WEAK, distance 1); A is UNKNOWN at distance 2.
        assert [entry.concept.name for entry in report.gaps] == ["B", "C", "A"]


def test_missing_target_raises(session_factory) -> None:
    with session_factory() as session:
        with pytest.raises(ValueError):
            GapDetector(session).detect(999)
