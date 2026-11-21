"""Learning routes: gap detection, recommendations, assessment generation and submission."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ConceptResponse,
    GapEntryResponse,
    GapReportResponse,
    GenerateAssessmentRequest,
    GenerateAssessmentResponse,
    RecommendationResponse,
    RecommendedTopicResponse,
    SubmitAssessmentRequest,
    SubmitAssessmentResponse,
)
from app.core.config import Settings
from app.db.repositories import KnowledgeRepository
from app.db.models import AssessmentAttempt, Concept, PracticeGuide
from app.learning.assessment import AssessmentService
from app.learning.gap_detector import GapDetector, GapEntry
from app.learning.mastery import MasteryService
from app.learning.recommender import Recommender
from app.llm.provider import LLMProvider


def make_learning_router(get_session, llm: LLMProvider | None, settings: Settings) -> APIRouter:
    router = APIRouter(tags=["learning"])

    @router.get("/learning/progress")
    def course_progress(session: Session = Depends(get_session)):
        graded = AssessmentAttempt.user_answer.is_not(None)
        total, tested = session.execute(select(
            func.count(AssessmentAttempt.id), func.count(func.distinct(AssessmentAttempt.concept_id))
        ).where(graded)).one()
        correct = session.scalar(select(func.count(AssessmentAttempt.id)).where(
            graded, AssessmentAttempt.result.is_(True)))
        concepts = session.scalar(select(func.count(Concept.id)))
        recent = session.execute(select(AssessmentAttempt, Concept.name, PracticeGuide)
            .join(Concept, Concept.id == AssessmentAttempt.concept_id)
            .outerjoin(PracticeGuide, PracticeGuide.attempt_id == AssessmentAttempt.id)
            .where(graded).order_by(AssessmentAttempt.id.desc()).limit(5))
        return {"total": total, "correct": correct, "untested": concepts - tested, "recent": [
            {"id": a.id, "concept": name, "question": a.question, "answer": a.user_answer,
             "correct": a.result, "hints": len(guide.hints) if guide else 0}
            for a, name, guide in recent
        ]}

    def build_gap_detector(session: Session) -> GapDetector:
        return GapDetector(
            session,
            mastered_threshold=settings.mastered_threshold,
            weak_threshold=settings.weak_threshold,
            min_evidence=settings.mastery_min_evidence,
        )

    @router.get("/learning/gaps/{concept_id}", response_model=GapReportResponse)
    def get_gaps(concept_id: int, session: Session = Depends(get_session)) -> GapReportResponse:
        try:
            report = build_gap_detector(session).detect(concept_id)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
        return GapReportResponse(
            target=ConceptResponse.model_validate(report.target),
            prerequisites=[_gap_entry(entry) for entry in report.prerequisites],
            gaps=[_gap_entry(entry) for entry in report.gaps],
        )

    @router.get("/learning/recommendation", response_model=RecommendationResponse)
    def get_recommendation(
        concept_id: int | None = Query(default=None),
        limit: int = Query(default=3, ge=1, le=10),
        session: Session = Depends(get_session),
    ) -> RecommendationResponse:
        topics = Recommender(session, build_gap_detector(session)).recommend(concept_id, limit)
        return RecommendationResponse(
            topics=[
                RecommendedTopicResponse(
                    concept=ConceptResponse.model_validate(topic.concept),
                    status=topic.status,
                    mastery=topic.mastery,
                    evidence_count=topic.evidence_count,
                    reason=topic.reason,
                )
                for topic in topics
            ]
        )

    @router.post("/assessment/generate", response_model=GenerateAssessmentResponse)
    def generate_assessment(
        request: GenerateAssessmentRequest, session: Session = Depends(get_session)
    ) -> GenerateAssessmentResponse:
        service = AssessmentService(session, llm)
        try:
            attempt = service.generate(request.concept_id, request.difficulty)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        session.commit()
        concept = KnowledgeRepository(session).get_concept(request.concept_id)
        return GenerateAssessmentResponse(
            attempt_id=attempt.id,
            concept_id=attempt.concept_id,
            concept_name=concept.name if concept else "",
            question=attempt.question,
            question_type=attempt.question_type,
            difficulty=attempt.difficulty,
        )

    @router.post("/assessment/submit", response_model=SubmitAssessmentResponse)
    def submit_assessment(
        request: SubmitAssessmentRequest, session: Session = Depends(get_session)
    ) -> SubmitAssessmentResponse:
        repository = KnowledgeRepository(session)
        mastery = MasteryService(session)
        pending = repository.get_attempt(request.attempt_id)
        if pending is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Assessment attempt not found.",
            )
        before = mastery.get_estimate(pending.concept_id)
        try:
            attempt, record, evaluation = AssessmentService(session, llm).submit(
                request.attempt_id, request.user_answer
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        session.commit()
        return SubmitAssessmentResponse(
            attempt_id=attempt.id,
            concept_id=attempt.concept_id,
            correct=evaluation.correct,
            score=evaluation.score,
            reasoning=evaluation.reasoning,
            identified_mistakes=evaluation.identified_mistakes,
            mastery_before=before,
            mastery_after=record.estimated_mastery,
            evidence_count=record.evidence_count,
        )

    return router


def _gap_entry(entry: GapEntry) -> GapEntryResponse:
    return GapEntryResponse(
        concept=ConceptResponse.model_validate(entry.concept),
        distance=entry.distance,
        status=entry.status,
        mastery=entry.mastery,
        evidence_count=entry.evidence_count,
        has_source_evidence=entry.has_source_evidence,
    )
