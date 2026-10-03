from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import ConceptDetailResponse, ConceptResponse
from app.db.repositories import KnowledgeRepository


def make_knowledge_router(get_session) -> APIRouter:
    router = APIRouter(prefix="/concepts", tags=["knowledge"])

    @router.get("", response_model=list[ConceptResponse])
    def list_concepts(
        query: str | None = Query(default=None, max_length=255), session: Session = Depends(get_session)
    ) -> list[ConceptResponse]:
        concepts = KnowledgeRepository(session).list_concepts(query)
        return [ConceptResponse.model_validate(concept) for concept in concepts]

    @router.get("/{concept_id}", response_model=ConceptDetailResponse)
    def get_concept(concept_id: int, session: Session = Depends(get_session)) -> ConceptDetailResponse:
        concept = KnowledgeRepository(session).get_concept(concept_id)
        if concept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        return ConceptDetailResponse.model_validate(concept)

    return router
