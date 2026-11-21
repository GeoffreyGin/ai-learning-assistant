from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    document_id: int
    text: str
    page_number: int | None
    chunk_index: int


class DocumentLabel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str


class DocumentResponse(DocumentLabel):
    file_type: str
    created_at: datetime


class DocumentDetailResponse(DocumentResponse):
    chunks: list[SourceChunkResponse]


class UploadDocumentResponse(BaseModel):
    document: DocumentResponse
    chunk_count: int
    extracted_mentions: int
    new_concept_count: int
    new_relationship_count: int = 0
    llm_fallback_chunks: int = 0


class GroundedClaimResponse(BaseModel):
    text: str
    source_chunk_id: int


class KnowledgeSummaryResponse(BaseModel):
    document_id: int
    overview: str
    key_concepts: list[str]
    claims: list[GroundedClaimResponse]


class ConceptLabel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class DirectoryResponse(BaseModel):
    documents: list[DocumentLabel]
    concepts: list[ConceptLabel]


class ConceptResponse(ConceptLabel):
    description: str
    created_at: datetime
    updated_at: datetime


class ConceptDetailResponse(ConceptResponse):
    source_chunks: list[SourceChunkResponse]


class PrerequisiteResponse(BaseModel):
    concept: ConceptResponse
    distance: int


class RelatedConceptResponse(BaseModel):
    concept: ConceptResponse
    relation_type: str
    confidence: float


class CreateConceptRequest(BaseModel):
    name: str
    description: str = ""


class UpdateConceptRequest(BaseModel):
    description: str


class CreateRelationshipRequest(BaseModel):
    source: str
    target: str
    relation_type: str
    confidence: float = 0.7


class RelationshipResponse(BaseModel):
    id: int
    source_concept_id: int
    target_concept_id: int
    relation_type: str
    confidence: float
    created: bool


class GraphNodeResponse(BaseModel):
    id: int
    name: str
    mastery: float | None


class GraphEdgeResponse(BaseModel):
    source: int
    target: int
    type: str
    confidence: float
    evidence_source_id: int | None = None


class GraphResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


class GapEntryResponse(BaseModel):
    concept: ConceptResponse
    distance: int
    status: str
    mastery: float | None
    evidence_count: int
    has_source_evidence: bool


class GapReportResponse(BaseModel):
    target: ConceptResponse
    prerequisites: list[GapEntryResponse]
    gaps: list[GapEntryResponse]


class RecommendedTopicResponse(BaseModel):
    concept: ConceptResponse
    status: str
    mastery: float | None
    evidence_count: int
    reason: str


class RecommendationResponse(BaseModel):
    topics: list[RecommendedTopicResponse]


class GenerateAssessmentRequest(BaseModel):
    concept_id: int
    difficulty: int | None = Field(default=None, ge=1, le=3)


class GenerateAssessmentResponse(BaseModel):
    attempt_id: int
    concept_id: int
    concept_name: str
    question: str
    question_type: str
    difficulty: int


class SubmitAssessmentRequest(BaseModel):
    attempt_id: int
    user_answer: str


class SubmitAssessmentResponse(BaseModel):
    attempt_id: int
    concept_id: int
    correct: bool
    score: float
    reasoning: str
    identified_mistakes: list[str]
    mastery_before: float | None
    mastery_after: float
    evidence_count: int


class AgentChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    document_id: int | None = Field(default=None, ge=1)
    concept_id: int | None = Field(default=None, ge=1)
    attempt_id: int | None = Field(default=None, ge=1)
    hint: bool = False
    step: int | None = Field(default=None, ge=1)


class PendingQuestionResponse(BaseModel):
    attempt_id: int
    concept_id: int
    concept_name: str
    question: str
    worked_steps: list[str] = Field(default_factory=list)
    hint_count: int = 0


class AgentActionResponse(BaseModel):
    tool: str
    detail: str


class AgentChatResponse(BaseModel):
    reply: str
    actions: list[AgentActionResponse]
    pending: PendingQuestionResponse | None


class AgentLogEntryResponse(BaseModel):
    timestamp: str
    tool: str
    detail: str
