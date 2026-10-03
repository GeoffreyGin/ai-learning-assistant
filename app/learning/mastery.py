"""Deterministic, evidence-based mastery estimation (spec §16).

Mastery starts at 0.0 with no evidence and only moves through recorded assessment
results. Correct answers increase it with diminishing returns; incorrect answers
decrease it proportionally to the current estimate (repeated mistakes cost more);
time without practice decays it slightly. All updates stay within [0, 1].
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import MasteryRecord
from app.db.repositories import KnowledgeRepository

LEARNING_RATE = 0.20  # maximum gain from one correct answer (at mastery 0)
FORGET_RATE = 0.20  # maximum loss from one incorrect answer (at mastery 1)
REPEAT_MISTAKE_PENALTY = 1.5  # extra loss when the previous attempt was also incorrect
DECAY_RATE = 0.01  # daily exponential decay, applied after the grace period
DECAY_GRACE_DAYS = 7  # days without practice before decay starts


def difficulty_weight(difficulty: int) -> float:
    """Difficulty 1..3 scales the update: easy answers count less, hard answers count more."""
    return (max(1, min(3, difficulty)) + 1) / 3


def clamp_mastery(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 3)


def update_mastery(
    previous: float, correct: bool, difficulty: int, repeated_mistake: bool = False
) -> float:
    """One deterministic step from `previous` mastery after a graded answer."""
    weight = difficulty_weight(difficulty)
    if correct:
        return clamp_mastery(previous + LEARNING_RATE * (1.0 - previous) * weight)
    loss = FORGET_RATE * previous * weight
    if repeated_mistake:
        loss *= REPEAT_MISTAKE_PENALTY
    return clamp_mastery(previous - loss)


def decayed_mastery(mastery: float, days_since_tested: float) -> float:
    """Mastery after `days_since_tested` days without practice."""
    if days_since_tested <= DECAY_GRACE_DAYS:
        return clamp_mastery(mastery)
    return clamp_mastery(mastery * math.exp(-DECAY_RATE * (days_since_tested - DECAY_GRACE_DAYS)))


def _days_between(earlier: datetime, later: datetime) -> float:
    # SQLite stores datetimes without timezone info; treat naive values as UTC.
    if earlier.tzinfo is None:
        earlier = earlier.replace(tzinfo=UTC)
    if later.tzinfo is None:
        later = later.replace(tzinfo=UTC)
    return (later - earlier).total_seconds() / 86_400


class MasteryService:
    def __init__(self, session: Session, now_fn=lambda: datetime.now(UTC)) -> None:
        self.session = session
        self.now_fn = now_fn

    def get_record(self, concept_id: int) -> MasteryRecord | None:
        return KnowledgeRepository(self.session).get_mastery_record(concept_id)

    def get_estimate(self, concept_id: int) -> float | None:
        """Current (decayed) mastery estimate, or None when no evidence exists."""
        record = self.get_record(concept_id)
        if record is None:
            return None
        return decayed_mastery(
            record.estimated_mastery, _days_between(record.last_tested_at, self.now_fn())
        )

    def record_result(
        self,
        concept_id: int,
        *,
        correct: bool,
        difficulty: int,
        exclude_attempt_id: int | None = None,
    ) -> MasteryRecord:
        """Fold one graded attempt into the concept's mastery record."""
        now = self.now_fn()
        repository = KnowledgeRepository(self.session)
        record = self.get_record(concept_id)
        previous = (
            0.0
            if record is None
            else decayed_mastery(
                record.estimated_mastery, _days_between(record.last_tested_at, now)
            )
        )
        repeated_mistake = False
        if record is not None:
            prior = repository.latest_attempt_for_concept(concept_id, exclude_id=exclude_attempt_id)
            repeated_mistake = prior is not None and prior.result is False
        estimated = update_mastery(previous, correct, difficulty, repeated_mistake)
        return repository.upsert_mastery_record(
            concept_id=concept_id,
            estimated_mastery=estimated,
            evidence_count=(record.evidence_count + 1) if record else 1,
            correct_count=(record.correct_count + int(correct)) if record else int(correct),
            incorrect_count=(record.incorrect_count + int(not correct))
            if record
            else int(not correct),
            last_tested_at=now,
        )
