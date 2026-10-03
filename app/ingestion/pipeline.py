from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.repositories import KnowledgeRepository
from app.ingestion.parsers import SUPPORTED_FILE_TYPES, chunk_sections, parse_file
from app.knowledge.extractor import ConceptExtractor


@dataclass(frozen=True)
class IngestionSummary:
    document: Document
    chunk_count: int
    concept_count: int
    new_concept_count: int


class IngestionService:
    def __init__(self, *, upload_dir: Path, extractor: ConceptExtractor) -> None:
        self.upload_dir = upload_dir
        self.extractor = extractor

    async def ingest(self, upload: UploadFile, session: Session) -> IngestionSummary:
        filename = upload.filename or "untitled.txt"
        suffix = Path(filename).suffix.casefold()
        if suffix not in SUPPORTED_FILE_TYPES:
            raise ValueError("Unsupported file type. Use PDF, Markdown, or TXT.")
        stored_path = self.upload_dir / f"{uuid4().hex}{suffix}"
        stored_path.write_bytes(await upload.read())
        try:
            parsed_chunks = chunk_sections(parse_file(stored_path))
            repository = KnowledgeRepository(session)
            document = repository.create_document(
                title=Path(filename).stem or "Untitled document", file_path=str(stored_path), file_type=suffix[1:]
            )
            mentions = 0
            new_concepts = 0
            for index, parsed_chunk in enumerate(parsed_chunks):
                chunk = repository.add_chunk(
                    document_id=document.id, text=parsed_chunk.text, page_number=parsed_chunk.page_number, chunk_index=index
                )
                for extracted in self.extractor.extract(parsed_chunk.text).concepts:
                    _, created = repository.resolve_concept(
                        name=extracted.name, description=extracted.description, source_chunk=chunk
                    )
                    mentions += 1
                    new_concepts += int(created)
            session.commit()
            session.refresh(document)
            return IngestionSummary(document, len(parsed_chunks), mentions, new_concepts)
        except Exception:
            session.rollback()
            stored_path.unlink(missing_ok=True)
            raise
