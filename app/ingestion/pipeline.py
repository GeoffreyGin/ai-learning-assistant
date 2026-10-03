from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models import Concept, Document, SourceChunk
from app.db.repositories import KnowledgeRepository
from app.ingestion.parsers import SUPPORTED_FILE_TYPES, chunk_sections, parse_file
from app.knowledge.extractor import ConceptExtractor, LocalConceptExtractor
from app.knowledge.resolver import ConceptResolver
from app.llm.provider import LLMError, LLMProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionSummary:
    document: Document
    chunk_count: int
    concept_count: int
    new_concept_count: int
    new_relationship_count: int
    llm_fallback_chunks: int


class IngestionService:
    def __init__(
        self,
        *,
        upload_dir: Path,
        extractor: ConceptExtractor,
        llm: LLMProvider | None = None,
    ) -> None:
        self.upload_dir = upload_dir
        self.extractor = extractor
        self.llm = llm

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
            resolver = ConceptResolver(repository, llm=self.llm)
            document = repository.create_document(
                title=Path(filename).stem or "Untitled document",
                file_path=str(stored_path),
                file_type=suffix[1:],
            )
            mentions = 0
            new_concepts = 0
            new_relationships = 0
            fallback_chunks = 0
            for index, parsed_chunk in enumerate(parsed_chunks):
                chunk = repository.add_chunk(
                    document_id=document.id,
                    text=parsed_chunk.text,
                    page_number=parsed_chunk.page_number,
                    chunk_index=index,
                )
                try:
                    result = self.extractor.extract(parsed_chunk.text)
                except LLMError as error:
                    # The LLM failed; degrade to the deterministic extractor for this chunk
                    # instead of losing the whole upload (spec §25).
                    logger.warning(
                        "LLM extraction failed for chunk %d; using local fallback: %s", index, error
                    )
                    result = LocalConceptExtractor().extract(parsed_chunk.text)
                    fallback_chunks += 1
                for extracted in result.concepts:
                    _, created = resolver.resolve(
                        extracted.name, extracted.description, source_chunk=chunk
                    )
                    mentions += 1
                    new_concepts += int(created)
                for relationship in result.relationships:
                    source = self._resolve_endpoint(resolver, relationship.source, chunk)
                    target = self._resolve_endpoint(resolver, relationship.target, chunk)
                    if source.id == target.id:
                        continue
                    _, created = repository.create_relationship(
                        source_concept_id=source.id,
                        target_concept_id=target.id,
                        relation_type=relationship.type,
                        confidence=relationship.confidence,
                        evidence_source_id=chunk.id,
                    )
                    new_relationships += int(created)
            session.commit()
            session.refresh(document)
            return IngestionSummary(
                document,
                len(parsed_chunks),
                mentions,
                new_concepts,
                new_relationships,
                fallback_chunks,
            )
        except Exception:
            session.rollback()
            stored_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _resolve_endpoint(resolver: ConceptResolver, name: str, chunk: SourceChunk) -> Concept:
        # A relationship may introduce a concept the text presupposes. Ground it only
        # when the name actually appears in the chunk text; otherwise it stays ungrounded.
        grounded_chunk = chunk if name.casefold() in chunk.text.casefold() else None
        concept, _ = resolver.resolve(name, description="", source_chunk=grounded_chunk)
        return concept
