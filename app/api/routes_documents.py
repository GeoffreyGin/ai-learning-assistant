from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    DocumentDetailResponse,
    DocumentResponse,
    GroundedClaimResponse,
    KnowledgeSummaryResponse,
    UploadDocumentResponse,
)
from app.db.repositories import KnowledgeRepository
from app.ingestion.pipeline import IngestionService
from app.knowledge.summarizer import LocalKnowledgeSummarizer


def make_documents_router(get_session, ingestion_service: IngestionService) -> APIRouter:
    router = APIRouter(prefix="/documents", tags=["documents"])

    @router.post(
        "/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_201_CREATED
    )
    async def upload_document(
        file: UploadFile = File(...), session: Session = Depends(get_session)
    ) -> UploadDocumentResponse:
        try:
            summary = await ingestion_service.ingest(file, session)
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
            ) from error
        return UploadDocumentResponse(
            document=DocumentResponse.model_validate(summary.document),
            chunk_count=summary.chunk_count,
            extracted_mentions=summary.concept_count,
            new_concept_count=summary.new_concept_count,
            new_relationship_count=summary.new_relationship_count,
            llm_fallback_chunks=summary.llm_fallback_chunks,
        )

    @router.get("", response_model=list[DocumentResponse])
    def list_documents(session: Session = Depends(get_session)) -> list[DocumentResponse]:
        return [
            DocumentResponse.model_validate(item)
            for item in KnowledgeRepository(session).list_documents()
        ]

    @router.post("/{document_id}/knowledge-summary", response_model=KnowledgeSummaryResponse)
    def create_knowledge_summary(
        document_id: int, session: Session = Depends(get_session)
    ) -> KnowledgeSummaryResponse:
        repository = KnowledgeRepository(session)
        document = repository.get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        summary = LocalKnowledgeSummarizer().summarize(
            document, repository.list_document_concepts(document_id)
        )
        return KnowledgeSummaryResponse(
            document_id=document.id,
            overview=summary.overview,
            key_concepts=summary.key_concepts,
            claims=[
                GroundedClaimResponse(text=claim.text, source_chunk_id=claim.source_chunk_id)
                for claim in summary.claims
            ],
        )

    @router.get("/{document_id}", response_model=DocumentDetailResponse)
    def get_document(
        document_id: int, session: Session = Depends(get_session)
    ) -> DocumentDetailResponse:
        document = KnowledgeRepository(session).get_document(document_id)
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
        return DocumentDetailResponse.model_validate(document)

    return router
