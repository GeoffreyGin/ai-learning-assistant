"""Knowledge routes: concepts, prerequisites, the graph view, and write endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    ConceptDetailResponse,
    ConceptResponse,
    CreateConceptRequest,
    CreateRelationshipRequest,
    DirectoryResponse,
    GraphResponse,
    PrerequisiteResponse,
    RelatedConceptResponse,
    RelationshipResponse,
    UpdateConceptRequest,
)
from app.db.repositories import KnowledgeRepository
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.relationship_service import RelationshipService
from app.knowledge.resolver import ConceptResolver
from app.learning.mastery import MasteryService
from app.llm.provider import LLMProvider


def make_knowledge_router(get_session, llm: LLMProvider | None) -> APIRouter:
    router = APIRouter(prefix="/concepts", tags=["knowledge"])

    @router.get("", response_model=list[ConceptResponse])
    def list_concepts(
        query: str | None = Query(default=None, max_length=255),
        session: Session = Depends(get_session),
    ) -> list[ConceptResponse]:
        concepts = KnowledgeRepository(session).list_concepts(query)
        return [ConceptResponse.model_validate(concept) for concept in concepts]

    @router.get("/{concept_id}", response_model=ConceptDetailResponse)
    def get_concept(
        concept_id: int, session: Session = Depends(get_session)
    ) -> ConceptDetailResponse:
        concept = KnowledgeRepository(session).get_concept(concept_id)
        if concept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        return ConceptDetailResponse.model_validate(concept)

    @router.get("/{concept_id}/prerequisites", response_model=list[PrerequisiteResponse])
    def get_prerequisites(
        concept_id: int, session: Session = Depends(get_session)
    ) -> list[PrerequisiteResponse]:
        repository = KnowledgeRepository(session)
        if repository.get_concept(concept_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        entries = []
        for related_id, distance in KnowledgeGraph(repository).prerequisites(concept_id):
            concept = repository.get_concept(related_id)
            if concept is not None:
                entries.append(
                    PrerequisiteResponse(
                        concept=ConceptResponse.model_validate(concept), distance=distance
                    )
                )
        return entries

    @router.get("/{concept_id}/related", response_model=list[RelatedConceptResponse])
    def get_related_concepts(
        concept_id: int, session: Session = Depends(get_session)
    ) -> list[RelatedConceptResponse]:
        repository = KnowledgeRepository(session)
        if repository.get_concept(concept_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        entries = []
        for related_id, relation_type, confidence in KnowledgeGraph(repository).related(concept_id):
            concept = repository.get_concept(related_id)
            if concept is not None:
                entries.append(
                    RelatedConceptResponse(
                        concept=ConceptResponse.model_validate(concept),
                        relation_type=relation_type,
                        confidence=confidence,
                    )
                )
        return entries

    @router.post("", response_model=ConceptResponse, status_code=status.HTTP_201_CREATED)
    def create_concept(
        request: CreateConceptRequest, session: Session = Depends(get_session)
    ) -> ConceptResponse:
        repository = KnowledgeRepository(session)
        try:
            concept, _ = ConceptResolver(repository, llm).resolve(request.name, request.description)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        session.commit()
        return ConceptResponse.model_validate(concept)

    @router.patch("/{concept_id}", response_model=ConceptResponse)
    def update_concept(
        concept_id: int, request: UpdateConceptRequest, session: Session = Depends(get_session)
    ) -> ConceptResponse:
        concept = KnowledgeRepository(session).update_concept(
            concept_id, description=request.description
        )
        if concept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        session.commit()
        return ConceptResponse.model_validate(concept)

    return router


def make_graph_router(get_session, llm: LLMProvider | None) -> APIRouter:
    router = APIRouter(tags=["knowledge"])

    @router.get("/directory", summary="List document titles, concept names and their IDs")
    def id_directory(session: Session = Depends(get_session)) -> DirectoryResponse:
        return DirectoryResponse.model_validate(KnowledgeRepository(session).id_directory())

    @router.get("/graph", response_model=GraphResponse)
    def get_graph(session: Session = Depends(get_session)) -> GraphResponse:
        repository = KnowledgeRepository(session)
        mastery = MasteryService(session)
        estimates = {
            concept.id: mastery.get_estimate(concept.id) for concept in repository.list_concepts()
        }
        return GraphResponse.model_validate(KnowledgeGraph(repository).serialize(estimates))

    @router.get("/passages/{passage_id}")
    def get_passage(passage_id: int, session: Session = Depends(get_session)):
        chunk = KnowledgeRepository(session).get_source_chunk(passage_id)
        if not chunk:
            raise HTTPException(404, "Passage not found.")
        return {"document_id": chunk.document_id, "title": chunk.document.title,
                "page": chunk.page_number, "text": chunk.text}

    @router.post(
        "/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED
    )
    def create_relationship(
        request: CreateRelationshipRequest, session: Session = Depends(get_session)
    ) -> RelationshipResponse:
        repository = KnowledgeRepository(session)
        service = RelationshipService(repository, ConceptResolver(repository, llm))
        try:
            result = service.create(
                source=request.source,
                target=request.target,
                relation_type=request.relation_type,
                confidence=request.confidence,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        session.commit()
        return RelationshipResponse.model_validate(result)

    return router
