"""Assessment generation and answer evaluation (spec §17-§18).

Generation and open-ended evaluation use the LLM when available and degrade to
deterministic fallbacks otherwise. Objective answers (true/false, numeric) are
always evaluated deterministically (spec: use deterministic checking where possible).
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.db.models import AssessmentAttempt, MasteryRecord
from app.db.repositories import KnowledgeRepository
from app.learning.mastery import MasteryService
from app.llm.provider import LLMError, LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

QUESTION_TYPES = frozenset(
    {"conceptual", "calculation", "application", "true_false", "short_answer"}
)

GENERATION_SYSTEM_PROMPT = """\
You write one assessment question that tests a specific concept.

Rules:
- The question must test the given concept only. Do not test other concepts.
- Difficulty 1 = basic recall, 2 = understanding, 3 = application or calculation.
- question_type: "conceptual", "calculation", "application", "true_false", or "short_answer".
- "expected_answer" is a short model answer (one to three sentences, or a number).
- "solution_outline" is a one-sentence hint about how to solve it.
- For true_false questions, expected_answer must be exactly "true" or "false".
- Prefer source material facts when excerpts are provided; otherwise use domain knowledge.
"""

EVALUATION_SYSTEM_PROMPT = """\
You grade a student's answer to an assessment question.

- Compare the answer against the expected answer for factual correctness.
- score: 1.0 fully correct, ~0.5 partially correct, 0.0 wrong. Partial credit is allowed.
- "correct": true when the answer is essentially right (score >= 0.7).
- List every specific mistake in "identified_mistakes" (empty when none).
"""


class GeneratedAssessment(BaseModel):
    concept: str = Field(min_length=1, max_length=255)
    difficulty: int = Field(ge=1, le=3)
    question_type: str
    question: str = Field(min_length=5)
    expected_answer: str = Field(min_length=1)
    solution_outline: str = Field(default="")

    @field_validator("question_type")
    @classmethod
    def check_type(cls, value: str) -> str:
        normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
        if normalized not in QUESTION_TYPES:
            allowed = ", ".join(sorted(QUESTION_TYPES))
            raise ValueError(f"Unsupported question type {value!r}. Use one of: {allowed}.")
        return normalized


class AnswerEvaluation(BaseModel):
    correct: bool
    score: float = Field(ge=0, le=1)
    reasoning: str = Field(default="")
    identified_mistakes: list[str] = Field(default_factory=list)


_TRUE_WORDS = frozenset({"true", "t", "yes", "y", "correct", "right", "对", "是", "真"})
_FALSE_WORDS = frozenset({"false", "f", "no", "n", "incorrect", "wrong", "错", "否", "假"})
_KEYWORD_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "are",
        "but",
        "not",
        "you",
        "all",
        "any",
        "can",
        "had",
        "her",
        "was",
        "one",
        "our",
        "out",
        "has",
        "his",
        "how",
        "its",
        "two",
        "may",
        "who",
        "did",
        "that",
        "this",
        "with",
        "have",
        "from",
        "they",
        "will",
        "what",
        "when",
        "your",
        "than",
        "then",
        "them",
        "these",
        "those",
        "their",
        "there",
        "which",
        "about",
        "would",
        "could",
        "should",
        "because",
        "between",
        "explain",
        "describe",
        "concept",
        "answer",
        "question",
    }
)


def difficulty_for_mastery(mastery: float | None) -> int:
    if mastery is None or mastery < 0.4:
        return 1
    if mastery < 0.8:
        return 2
    return 3


def evaluate_true_false(expected_answer: str, user_answer: str) -> AnswerEvaluation:
    expected = _normalize_true_false(expected_answer)
    given = _normalize_true_false(user_answer)
    if expected is None:
        return evaluate_keyword_overlap(expected_answer, user_answer)
    if given is None:
        return AnswerEvaluation(
            correct=False,
            score=0.0,
            reasoning="Could not parse a true/false answer from the response.",
            identified_mistakes=["Answer should be true or false."],
        )
    correct = given == expected
    return AnswerEvaluation(
        correct=correct,
        score=1.0 if correct else 0.0,
        reasoning=f"Expected {expected}, got {given}.",
    )


def evaluate_numeric(
    expected_answer: str, user_answer: str, tolerance: float = 0.01
) -> AnswerEvaluation | None:
    """Returns None when the expected answer is not numeric, so callers can fall through."""
    expected = _extract_number(expected_answer)
    if expected is None:
        return None
    given_values = _extract_numbers(user_answer)
    if not given_values:
        return AnswerEvaluation(
            correct=False,
            score=0.0,
            reasoning="No numeric value found in the answer.",
            identified_mistakes=["Answer should contain a number."],
        )
    correct = any(
        abs(value - expected) <= max(1e-9, tolerance * abs(expected)) for value in given_values
    )
    return AnswerEvaluation(
        correct=correct,
        score=1.0 if correct else 0.0,
        reasoning=f"Expected about {expected}, got {given_values[0]}.",
    )


def evaluate_keyword_overlap(expected_answer: str, user_answer: str) -> AnswerEvaluation:
    """Deterministic open-ended fallback: fraction of significant expected keywords covered."""
    expected_keywords = _keywords(expected_answer)
    given_words = set(_keywords(user_answer))
    if not expected_keywords:
        return AnswerEvaluation(
            correct=False, score=0.0, reasoning="No expected keywords available."
        )
    missing = [word for word in expected_keywords if word not in given_words]
    score = 1.0 - len(missing) / len(expected_keywords)
    return AnswerEvaluation(
        correct=score >= 0.6,
        score=round(score, 3),
        reasoning=f"Keyword coverage {score:.0%} of the expected answer.",
        identified_mistakes=[f"Missing key point: {word}" for word in missing],
    )


def _normalize_true_false(text: str) -> bool | None:
    words = re.findall(r"[a-z]+|[一-鿿]", text.casefold())
    if any(word in _TRUE_WORDS for word in words):
        return True
    if any(word in _FALSE_WORDS for word in words):
        return False
    return None


def _extract_numbers(text: str) -> list[float]:
    cleaned = text.replace(",", "")
    return [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", cleaned)]


def _extract_number(text: str) -> float | None:
    values = _extract_numbers(text)
    return values[0] if values else None


def _keywords(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[a-z0-9]+", text.casefold())
        if len(word) >= 3 and word not in _KEYWORD_STOPWORDS
    ]


class AssessmentService:
    def __init__(self, session: Session, llm: LLMProvider | None = None) -> None:
        self.session = session
        self.llm = llm
        self.repository = KnowledgeRepository(session)
        self.mastery = MasteryService(session)

    def generate(self, concept_id: int, difficulty: int | None = None) -> AssessmentAttempt:
        concept = self.repository.get_concept(concept_id)
        if concept is None:
            raise ValueError(f"Concept {concept_id} not found.")
        if difficulty is None:
            difficulty = difficulty_for_mastery(self.mastery.get_estimate(concept_id))
        generated = self._generate_question(concept_id, difficulty)
        return self.repository.create_attempt(
            concept_id=concept_id,
            question_type=generated.question_type,
            question=generated.question,
            expected_answer=generated.expected_answer,
            solution_outline=generated.solution_outline,
            difficulty=generated.difficulty,
        )

    def submit(
        self, attempt_id: int, user_answer: str
    ) -> tuple[AssessmentAttempt, MasteryRecord, AnswerEvaluation]:
        attempt = self.repository.get_attempt(attempt_id)
        if attempt is None:
            raise ValueError("Assessment attempt not found.")
        if attempt.user_answer is not None:
            raise ValueError("This question was already answered.")
        evaluation = self.evaluate(attempt, user_answer)
        self.repository.complete_attempt(
            attempt_id,
            user_answer=user_answer.strip(),
            result=evaluation.correct,
            score=evaluation.score,
            evaluation=evaluation.model_dump_json(),
        )
        record = self.mastery.record_result(
            attempt.concept_id,
            correct=evaluation.correct,
            difficulty=attempt.difficulty,
            exclude_attempt_id=attempt.id,
        )
        return attempt, record, evaluation

    def evaluate(self, attempt: AssessmentAttempt, user_answer: str) -> AnswerEvaluation:
        normalized = user_answer.strip()
        if attempt.question_type == "true_false":
            return evaluate_true_false(attempt.expected_answer, normalized)
        numeric = evaluate_numeric(attempt.expected_answer, normalized)
        if numeric is not None:
            return numeric
        if self.llm is not None:
            try:
                return self.llm.structured_generate(
                    [
                        LLMMessage(role="system", content=EVALUATION_SYSTEM_PROMPT),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Concept: {attempt.concept.name}\n"
                                f"Question ({attempt.question_type}): {attempt.question}\n"
                                f"Expected answer: {attempt.expected_answer}\n"
                                f"Solution outline: {attempt.solution_outline}\n\n"
                                f"Student answer: {normalized}"
                            ),
                        ),
                    ],
                    schema=AnswerEvaluation,
                    max_tokens=1024,
                    temperature=0.0,
                )
            except LLMError as error:
                logger.warning("LLM evaluation failed; using keyword fallback: %s", error)
        return evaluate_keyword_overlap(attempt.expected_answer, normalized)

    def _generate_question(self, concept_id: int, difficulty: int) -> GeneratedAssessment:
        concept = self.repository.get_concept(concept_id)
        assert concept is not None
        source_excerpts = (
            "\n\n".join(chunk.text for chunk in concept.source_chunks[:3]) or "none provided"
        )
        if self.llm is not None:
            try:
                return self.llm.structured_generate(
                    [
                        LLMMessage(role="system", content=GENERATION_SYSTEM_PROMPT),
                        LLMMessage(
                            role="user",
                            content=(
                                f"Concept: {concept.name}\n"
                                f"Concept description: {concept.description or 'not available'}\n"
                                f"Source excerpts: {source_excerpts}\n\n"
                                f"Generate ONE question at difficulty {difficulty}."
                            ),
                        ),
                    ],
                    schema=GeneratedAssessment,
                    max_tokens=2048,
                    temperature=0.4,
                )
            except LLMError as error:
                logger.warning("LLM generation failed; using template fallback: %s", error)
        return GeneratedAssessment(
            concept=concept.name,
            difficulty=difficulty,
            question_type="short_answer",
            question=f"In your own words, explain the concept '{concept.name}' and why it matters.",
            expected_answer=(
                concept.description
                or (concept.source_chunks[0].text if concept.source_chunks else concept.name)
            ),
            solution_outline="Refer to the definition and give one concrete reason it matters.",
        )
