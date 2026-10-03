"""Assessment generation and evaluation tests (spec §17, §18, §26)."""

import pytest

from app.learning.assessment import (
    AnswerEvaluation,
    AssessmentService,
    GeneratedAssessment,
    difficulty_for_mastery,
    evaluate_keyword_overlap,
    evaluate_numeric,
    evaluate_true_false,
)
from app.llm.provider import LLMError


def test_true_false_evaluation_accepts_synonyms() -> None:
    assert evaluate_true_false("true", "yes").correct is True
    assert evaluate_true_false("true", "false").correct is False
    assert evaluate_true_false("false", "no").correct is True
    assert evaluate_true_false("false", "yes").correct is False


def test_true_false_unparseable_answer_scores_zero() -> None:
    evaluation = evaluate_true_false("true", "banana")
    assert evaluation.correct is False
    assert evaluation.score == 0.0


def test_numeric_evaluation_uses_tolerance() -> None:
    assert evaluate_numeric("42", "The answer is 42").correct is True
    assert evaluate_numeric("42", "41.9").correct is True  # within 1%
    assert evaluate_numeric("42", "10").correct is False
    assert evaluate_numeric("not a number", "whatever") is None


def test_numeric_evaluation_requires_a_number() -> None:
    evaluation = evaluate_numeric("42", "I have no idea")
    assert evaluation.correct is False
    assert evaluation.identified_mistakes


def test_keyword_overlap_scores_partial_answers() -> None:
    evaluation = evaluate_keyword_overlap(
        "A stochastic process models random movement over time.",
        "A process models random movement.",
    )
    assert 0.0 < evaluation.score < 1.0
    assert evaluation.identified_mistakes


def test_generate_creates_pending_attempt_with_fake_llm(session_factory, seed, fake_llm) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]
    fake_llm.structured[GeneratedAssessment] = GeneratedAssessment(
        concept="Brownian Motion",
        difficulty=2,
        question_type="true_false",
        question="Is Brownian Motion a stochastic process?",
        expected_answer="true",
        solution_outline="Check the definition.",
    )
    with session_factory() as session:
        service = AssessmentService(session, fake_llm)
        attempt = service.generate(concept.id)
        assert attempt.user_answer is None
        session.commit()
        completed, record, evaluation = service.submit(attempt.id, "yes")
        assert evaluation.correct is True
        assert evaluation.score == 1.0
        assert record.estimated_mastery == 0.2
        assert completed.user_answer == "yes"
        session.commit()


def test_generate_falls_back_to_template_without_llm(session_factory, seed) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]
    with session_factory() as session:
        attempt = AssessmentService(session).generate(concept.id)
        assert attempt.question_type == "short_answer"
        assert "Brownian Motion" in attempt.question


def test_submit_twice_is_rejected(session_factory, seed) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]
    with session_factory() as session:
        service = AssessmentService(session)
        attempt = service.generate(concept.id)
        session.commit()
        service.submit(attempt.id, "an answer")
        session.commit()
        with pytest.raises(ValueError, match="already answered"):
            service.submit(attempt.id, "another answer")


def test_llm_evaluation_falls_back_on_llm_error(session_factory, seed, fake_llm) -> None:
    concept = seed(["Brownian Motion"])["Brownian Motion"]

    def raise_error(messages):
        raise LLMError("provider down")

    fake_llm.structured[GeneratedAssessment] = GeneratedAssessment(
        concept="Brownian Motion",
        difficulty=1,
        question_type="short_answer",
        question="What is Brownian Motion?",
        expected_answer="A stochastic process that models random movement.",
        solution_outline="Use the definition.",
    )
    fake_llm.structured[AnswerEvaluation] = raise_error
    with session_factory() as session:
        service = AssessmentService(session, fake_llm)
        attempt = service.generate(concept.id)
        evaluation = service.evaluate(attempt, "a stochastic process models random movement")
        assert 0.0 <= evaluation.score <= 1.0


def test_difficulty_pick_by_mastery() -> None:
    assert difficulty_for_mastery(None) == 1
    assert difficulty_for_mastery(0.2) == 1
    assert difficulty_for_mastery(0.5) == 2
    assert difficulty_for_mastery(0.9) == 3
