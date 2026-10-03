from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

concept_source_chunks = Table(
    "concept_source_chunks",
    Base.metadata,
    Column("concept_id", ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True),
    Column("source_chunk_id", ForeignKey("source_chunks.id", ondelete="CASCADE"), primary_key=True),
)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024))
    file_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    chunks: Mapped[list[SourceChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="SourceChunk.chunk_index"
    )


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    document: Mapped[Document] = relationship(back_populates="chunks")
    concepts: Mapped[list[Concept]] = relationship(
        secondary=concept_source_chunks, back_populates="source_chunks"
    )


class Concept(Base):
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    source_chunks: Mapped[list[SourceChunk]] = relationship(
        secondary=concept_source_chunks, back_populates="concepts"
    )


class Relationship(Base):
    """Directed relation between concepts. See app/knowledge/relations.py for types."""

    __tablename__ = "relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_concept_id", "target_concept_id", "relation_type", name="uq_relationship_triple"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source_concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    target_concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(40))
    confidence: Mapped[float] = mapped_column(Float)
    evidence_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("source_chunks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MasteryRecord(Base):
    """Evidence-based mastery estimate for one concept (spec §10, §16)."""

    __tablename__ = "mastery_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(
        ForeignKey("concepts.id", ondelete="CASCADE"), unique=True
    )
    estimated_mastery: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    concept: Mapped[Concept] = relationship()


class AssessmentAttempt(Base):
    """One generated question and its outcome (spec §10, §17, §18)."""

    __tablename__ = "assessment_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    question_type: Mapped[str] = mapped_column(String(40))
    question: Mapped[str] = mapped_column(Text)
    expected_answer: Mapped[str] = mapped_column(Text)
    solution_outline: Mapped[str] = mapped_column(Text, default="")
    difficulty: Mapped[int] = mapped_column(Integer, default=2)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON: reasoning + mistakes
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    concept: Mapped[Concept] = relationship()
