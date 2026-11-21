from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AssessmentAttempt,
    Concept,
    Document,
    MasteryRecord,
    Relationship,
    SourceChunk,
)


def normalize_concept_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    plain = re.sub(r"[’']s\b", "", plain, flags=re.IGNORECASE)
    words = re.findall(r"[a-z0-9]+", plain.casefold())
    return " ".join(words)


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def id_directory(self) -> dict:
        documents = select(Document.id, Document.title).order_by(Document.title, Document.id)
        concepts = select(Concept.id, Concept.name).order_by(Concept.name, Concept.id)
        return {
            "documents": self.session.execute(documents).mappings().all(),
            "concepts": self.session.execute(concepts).mappings().all(),
        }

    # -- Documents -------------------------------------------------------

    def create_document(self, *, title: str, file_path: str, file_type: str) -> Document:
        document = Document(title=title, file_path=file_path, file_type=file_type)
        self.session.add(document)
        self.session.flush()
        return document

    def add_chunk(
        self, *, document_id: int, text: str, page_number: int | None, chunk_index: int
    ) -> SourceChunk:
        chunk = SourceChunk(
            document_id=document_id, text=text, page_number=page_number, chunk_index=chunk_index
        )
        self.session.add(chunk)
        self.session.flush()
        return chunk

    def list_documents(self) -> list[Document]:
        query = (
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
        return list(self.session.scalars(query))

    def get_document(self, document_id: int) -> Document | None:
        query = (
            select(Document)
            .options(selectinload(Document.chunks))
            .where(Document.id == document_id)
        )
        return self.session.scalar(query)

    def search_documents(self, query: str) -> list[Document]:
        pattern = f"%{query.strip()}%"
        statement = (
            select(Document)
            .outerjoin(SourceChunk, SourceChunk.document_id == Document.id)
            .where(or_(Document.title.ilike(pattern), SourceChunk.text.ilike(pattern)))
            .distinct()
            .order_by(Document.created_at.desc())
        )
        return list(self.session.scalars(statement))

    def list_document_concepts(self, document_id: int) -> list[Concept]:
        statement = (
            select(Concept)
            .join(Concept.source_chunks)
            .where(SourceChunk.document_id == document_id)
            .order_by(Concept.name)
        )
        return list(self.session.scalars(statement).unique())

    def get_source_chunk(self, chunk_id: int) -> SourceChunk | None:
        return self.session.get(SourceChunk, chunk_id)

    # -- Concepts ---------------------------------------------------------

    def get_concept_by_normalized(self, normalized_name: str) -> Concept | None:
        return self.session.scalar(
            select(Concept).where(Concept.normalized_name == normalized_name)
        )

    def create_concept(
        self, *, name: str, description: str = "", source_chunk: SourceChunk | None = None
    ) -> Concept:
        normalized_name = normalize_concept_name(name)
        if not normalized_name:
            raise ValueError("Concept name must contain letters or numbers.")
        concept = Concept(
            name=name.strip(), normalized_name=normalized_name, description=description.strip()
        )
        if source_chunk is not None:
            concept.source_chunks.append(source_chunk)
        self.session.add(concept)
        self.session.flush()
        return concept

    def attach_source_chunk(self, concept: Concept, source_chunk: SourceChunk) -> bool:
        if source_chunk in concept.source_chunks:
            return False
        concept.source_chunks.append(source_chunk)
        self.session.flush()
        return True

    def list_concepts(self, query: str | None = None) -> list[Concept]:
        statement = (
            select(Concept).options(selectinload(Concept.source_chunks)).order_by(Concept.name)
        )
        if query:
            statement = statement.where(Concept.name.ilike(f"%{query.strip()}%"))
        return list(self.session.scalars(statement))

    def get_concept(self, concept_id: int) -> Concept | None:
        query = (
            select(Concept)
            .options(selectinload(Concept.source_chunks))
            .where(Concept.id == concept_id)
        )
        return self.session.scalar(query)

    def update_concept(
        self, concept_id: int, *, name: str | None = None, description: str | None = None
    ) -> Concept | None:
        concept = self.session.get(Concept, concept_id)
        if concept is None:
            return None
        if name is not None and name.strip():
            concept.name = name.strip()
        if description is not None:
            concept.description = description.strip()
        self.session.flush()
        return concept

    # -- Relationships -----------------------------------------------------

    def create_relationship(
        self,
        *,
        source_concept_id: int,
        target_concept_id: int,
        relation_type: str,
        confidence: float,
        evidence_source_id: int | None = None,
    ) -> tuple[Relationship, bool]:
        """Upsert by (source, target, type); an existing edge keeps the higher confidence."""
        existing = self.session.scalar(
            select(Relationship).where(
                Relationship.source_concept_id == source_concept_id,
                Relationship.target_concept_id == target_concept_id,
                Relationship.relation_type == relation_type,
            )
        )
        if existing is not None:
            existing.confidence = max(existing.confidence, confidence)
            self.session.flush()
            return existing, False
        relationship = Relationship(
            source_concept_id=source_concept_id,
            target_concept_id=target_concept_id,
            relation_type=relation_type,
            confidence=confidence,
            evidence_source_id=evidence_source_id,
        )
        self.session.add(relationship)
        self.session.flush()
        return relationship, True

    def list_relationships(self) -> list[Relationship]:
        return list(self.session.scalars(select(Relationship)))

    # -- Mastery -----------------------------------------------------------

    def get_mastery_record(self, concept_id: int) -> MasteryRecord | None:
        return self.session.scalar(
            select(MasteryRecord).where(MasteryRecord.concept_id == concept_id)
        )

    def upsert_mastery_record(
        self,
        *,
        concept_id: int,
        estimated_mastery: float,
        evidence_count: int,
        correct_count: int,
        incorrect_count: int,
        last_tested_at: datetime,
    ) -> MasteryRecord:
        record = self.get_mastery_record(concept_id)
        if record is None:
            record = MasteryRecord(concept_id=concept_id)
            self.session.add(record)
        record.estimated_mastery = estimated_mastery
        record.evidence_count = evidence_count
        record.correct_count = correct_count
        record.incorrect_count = incorrect_count
        record.last_tested_at = last_tested_at
        self.session.flush()
        return record

    # -- Assessments ---------------------------------------------------------

    def create_attempt(
        self,
        *,
        concept_id: int,
        question_type: str,
        question: str,
        expected_answer: str,
        solution_outline: str,
        difficulty: int,
    ) -> AssessmentAttempt:
        attempt = AssessmentAttempt(
            concept_id=concept_id,
            question_type=question_type,
            question=question,
            expected_answer=expected_answer,
            solution_outline=solution_outline,
            difficulty=difficulty,
        )
        self.session.add(attempt)
        self.session.flush()
        return attempt

    def get_attempt(self, attempt_id: int) -> AssessmentAttempt | None:
        return self.session.get(AssessmentAttempt, attempt_id)

    def latest_pending_attempt(self, *, max_age_hours: int = 24) -> AssessmentAttempt | None:
        """Most recent generated-but-unanswered question, within a freshness window."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        statement = (
            select(AssessmentAttempt)
            .where(AssessmentAttempt.user_answer.is_(None), AssessmentAttempt.created_at >= cutoff)
            .order_by(AssessmentAttempt.created_at.desc())
        )
        return self.session.scalar(statement)

    def latest_attempt_for_concept(
        self, concept_id: int, *, exclude_id: int | None = None
    ) -> AssessmentAttempt | None:
        statement = (
            select(AssessmentAttempt)
            .where(AssessmentAttempt.concept_id == concept_id)
            .order_by(AssessmentAttempt.created_at.desc())
        )
        if exclude_id is not None:
            statement = statement.where(AssessmentAttempt.id != exclude_id)
        return self.session.scalar(statement)

    def complete_attempt(
        self,
        attempt_id: int,
        *,
        user_answer: str,
        result: bool,
        score: float,
        evaluation: str,
    ) -> AssessmentAttempt | None:
        attempt = self.session.get(AssessmentAttempt, attempt_id)
        if attempt is None:
            return None
        attempt.user_answer = user_answer
        attempt.result = result
        attempt.score = score
        attempt.evaluation = evaluation
        self.session.flush()
        return attempt
