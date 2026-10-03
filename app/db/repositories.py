from __future__ import annotations

import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Concept, Document, SourceChunk


def normalize_concept_name(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    plain = re.sub(r"[’']s\b", "", plain, flags=re.IGNORECASE)
    words = re.findall(r"[a-z0-9]+", plain.casefold())
    return " ".join(words)


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_document(self, *, title: str, file_path: str, file_type: str) -> Document:
        document = Document(title=title, file_path=file_path, file_type=file_type)
        self.session.add(document)
        self.session.flush()
        return document

    def add_chunk(self, *, document_id: int, text: str, page_number: int | None, chunk_index: int) -> SourceChunk:
        chunk = SourceChunk(document_id=document_id, text=text, page_number=page_number, chunk_index=chunk_index)
        self.session.add(chunk)
        self.session.flush()
        return chunk

    def resolve_concept(self, *, name: str, description: str, source_chunk: SourceChunk) -> tuple[Concept, bool]:
        normalized_name = normalize_concept_name(name)
        if not normalized_name:
            raise ValueError("Concept name must contain letters or numbers.")
        concept = self.session.scalar(select(Concept).where(Concept.normalized_name == normalized_name))
        created = concept is None
        if concept is None:
            concept = Concept(name=name.strip(), normalized_name=normalized_name, description=description.strip())
            self.session.add(concept)
            self.session.flush()
        elif not concept.description and description.strip():
            concept.description = description.strip()
        if source_chunk not in concept.source_chunks:
            concept.source_chunks.append(source_chunk)
        return concept, created

    def list_documents(self) -> list[Document]:
        query = select(Document).options(selectinload(Document.chunks)).order_by(Document.created_at.desc())
        return list(self.session.scalars(query))

    def get_document(self, document_id: int) -> Document | None:
        query = select(Document).options(selectinload(Document.chunks)).where(Document.id == document_id)
        return self.session.scalar(query)

    def list_document_concepts(self, document_id: int) -> list[Concept]:
        statement = (
            select(Concept)
            .join(Concept.source_chunks)
            .where(SourceChunk.document_id == document_id)
            .order_by(Concept.name)
        )
        return list(self.session.scalars(statement).unique())

    def list_concepts(self, query: str | None = None) -> list[Concept]:
        statement = select(Concept).options(selectinload(Concept.source_chunks)).order_by(Concept.name)
        if query:
            statement = statement.where(Concept.name.ilike(f"%{query.strip()}%"))
        return list(self.session.scalars(statement))

    def get_concept(self, concept_id: int) -> Concept | None:
        query = select(Concept).options(selectinload(Concept.source_chunks)).where(Concept.id == concept_id)
        return self.session.scalar(query)
