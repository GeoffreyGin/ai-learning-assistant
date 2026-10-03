from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    text: str
    page_number: int | None
    chunk_index: int


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    file_type: str
    created_at: datetime


class DocumentDetailResponse(DocumentResponse):
    chunks: list[SourceChunkResponse]


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    chunk_count: int
    extracted_mentions: int
    new_concept_count: int


class GroundedClaimResponse(BaseModel):
    text: str
    source_chunk_id: int


class KnowledgeSummaryResponse(BaseModel):
    document_id: int
    overview: str
    key_concepts: list[str]
    claims: list[GroundedClaimResponse]


class ConceptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class ConceptDetailResponse(ConceptResponse):
    source_chunks: list[SourceChunkResponse]
