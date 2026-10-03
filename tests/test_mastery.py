"""Mastery estimation tests (spec §16, §26): deterministic, bounded, evidence-based."""

from datetime import UTC, datetime, timedelta

from app.db.repositories import KnowledgeRepository
from app.learning.mastery import MasteryService, decayed_mastery, update_mastery


def test_correct_answer_increases_mastery() -> None:
    assert update_mastery(0.6, True, 2) > 0.6


def test_incorrect_answer_decreases_mastery() -> None:
    assert update_mastery(0.6, False, 2) < 0.6


def test_mastery_stays_within_bounds() -> None:
    mastery = 1.0
    for _ in range(50):
        mastery = update_mastery(mastery, True, 3)
    assert 0.0 <= mastery <= 1.0
    mastery = 0.0
    for _ in range(50):
        mastery = update_mastery(mastery, False, 3)
    assert 0.0 <= mastery <= 1.0


def test_repeated_correct_answers_gain_less() -> None:
    first_gain = update_mastery(0.2, True, 2) - 0.2
    second_gain = update_mastery(0.5, True, 2) - 0.5
    assert second_gain < first_gain


def test_first_correct_answer_matches_spec_example() -> None:
    # Spec §28: Ito's Lemma starts at 0.20 after first success.
    assert update_mastery(0.0, True, 2) == 0.2


def test_repeated_mistake_penalizes_more() -> None:
    plain_loss = 0.6 - update_mastery(0.6, False, 2)
    repeated_loss = 0.6 - update_mastery(0.6, False, 2, repeated_mistake=True)
    assert repeated_loss > plain_loss


def test_harder_correct_answers_count_more() -> None:
    assert update_mastery(0.0, True, 3) > update_mastery(0.0, True, 1)


def test_decay_starts_after_grace_period_and_is_slight() -> None:
    assert decayed_mastery(0.8, 7) == 0.8
    assert 0.5 < decayed_mastery(0.8, 30) < 0.8


def test_service_creates_record_on_first_result(session_factory, seed) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]
    with session_factory() as session:
        service = MasteryService(session)
        record = service.record_result(concept.id, correct=True, difficulty=2)
        assert record.estimated_mastery == 0.2
        assert record.evidence_count == 1
        assert record.correct_count == 1
        assert record.incorrect_count == 0
        session.commit()


def test_estimate_is_none_without_evidence(session_factory, seed) -> None:
    concept = seed(["Ito's Lemma"])["Ito's Lemma"]
    with session_factory() as session:
        assert MasteryService(session).get_estimate(concept.id) is None


def test_estimate_decays_after_long_gap(session_factory, seed) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]
    with session_factory() as session:
        service = MasteryService(session)
        service.record_result(concept.id, correct=True, difficulty=2)
        session.commit()
        record = service.get_record(concept.id)
        record.last_tested_at = datetime.now(UTC) - timedelta(days=30)
        session.commit()
        assert service.get_estimate(concept.id) < record.estimated_mastery


def test_service_penalizes_repeated_mistakes(session_factory, seed) -> None:
    # Both concepts sit at mastery 0.5. Concept A's latest attempt was correct,
    # concept B's was incorrect. The same new incorrect answer must cost B more
    # (spec: repeated mistakes are weighted evidence).
    concepts = seed(["A", "B"])
    now = datetime.now(UTC)
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        service = MasteryService(session)
        for name, prior_correct in (("A", True), ("B", False)):
            repository.upsert_mastery_record(
                concept_id=concepts[name].id,
                estimated_mastery=0.5,
                evidence_count=1,
                correct_count=int(prior_correct),
                incorrect_count=int(not prior_correct),
                last_tested_at=now,
            )
            prior = repository.create_attempt(
                concept_id=concepts[name].id,
                question_type="true_false",
                question="Is it true?",
                expected_answer="true",
                solution_outline="",
                difficulty=2,
            )
            repository.complete_attempt(
                prior.id,
                user_answer="yes" if prior_correct else "no",
                result=prior_correct,
                score=1.0 if prior_correct else 0.0,
                evaluation="{}",
            )
        session.commit()

        results = {}
        for name in ("A", "B"):
            current = repository.create_attempt(
                concept_id=concepts[name].id,
                question_type="true_false",
                question="Is it true?",
                expected_answer="true",
                solution_outline="",
                difficulty=2,
            )
            repository.complete_attempt(
                current.id, user_answer="no", result=False, score=0.0, evaluation="{}"
            )
            results[name] = service.record_result(
                concepts[name].id, correct=False, difficulty=2, exclude_attempt_id=current.id
            )

        assert results["B"].estimated_mastery < results["A"].estimated_mastery
