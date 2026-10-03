"""The agent's explicit tool set (spec §13). Every call is logged (spec §24, Rule 7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agent.logging import ActionLogger
from app.core.config import Settings
from app.db.models import Concept
from app.db.repositories import KnowledgeRepository
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.relationship_service import RelationshipService
from app.knowledge.resolver import ConceptResolver
from app.learning.assessment import AssessmentService
from app.learning.gap_detector import GapDetector
from app.learning.mastery import MasteryService
from app.learning.recommender import Recommender
from app.llm.provider import LLMProvider


def concept_dict(concept: Concept) -> dict:
    return {
        "id": concept.id,
        "name": concept.name,
        "description": concept.description,
        "source_chunk_count": len(concept.source_chunks),
    }


class ToolSet:
    def __init__(
        self,
        session: Session,
        *,
        llm: LLMProvider | None,
        settings: Settings,
        logger: ActionLogger,
    ) -> None:
        self.session = session
        self.llm = llm
        self.logger = logger
        self.repository = KnowledgeRepository(session)
        self.graph = KnowledgeGraph(self.repository)
        self.mastery = MasteryService(session)
        self.gap_detector = GapDetector(
            session,
            mastered_threshold=settings.mastered_threshold,
            weak_threshold=settings.weak_threshold,
            min_evidence=settings.mastery_min_evidence,
        )
        self.assessment = AssessmentService(session, llm)
        self.recommender = Recommender(session, self.gap_detector)
        self.resolver = ConceptResolver(self.repository, llm)

    # -- Knowledge tools -----------------------------------------------------

    def search_concepts(self, query: str) -> dict:
        concepts = self.repository.list_concepts(query)[:10]
        self.logger.log("search_concepts", f"query={query!r} -> {len(concepts)} result(s)")
        return {"concepts": [concept_dict(concept) for concept in concepts]}

    def get_concept(self, concept_id: int) -> dict:
        concept = self.repository.get_concept(concept_id)
        self.logger.log(
            "get_concept", f"concept_id={concept_id} -> {concept.name if concept else 'not found'}"
        )
        if concept is None:
            raise ValueError(f"Concept {concept_id} not found.")
        data = concept_dict(concept)
        data["source_chunk_ids"] = [chunk.id for chunk in concept.source_chunks]
        mastery = self.mastery.get_estimate(concept_id)
        data["mastery"] = mastery
        return data

    def get_prerequisites(self, concept_id: int) -> dict:
        prerequisites = self.graph.prerequisites(concept_id)
        entries = []
        for related_id, distance in prerequisites:
            concept = self.repository.get_concept(related_id)
            if concept is not None:
                entries.append({"concept": concept_dict(concept), "distance": distance})
        self.logger.log(
            "get_prerequisites", f"concept_id={concept_id} -> {len(entries)} prerequisite(s)"
        )
        return {"prerequisites": entries}

    def get_related_concepts(self, concept_id: int) -> dict:
        related = self.graph.related(concept_id)
        entries = []
        for related_id, relation_type, confidence in related:
            concept = self.repository.get_concept(related_id)
            if concept is not None:
                entries.append(
                    {
                        "concept": concept_dict(concept),
                        "relation_type": relation_type,
                        "confidence": confidence,
                    }
                )
        self.logger.log(
            "get_related_concepts", f"concept_id={concept_id} -> {len(entries)} related concept(s)"
        )
        return {"related": entries}

    def search_documents(self, query: str) -> dict:
        documents = self.repository.search_documents(query)[:10]
        self.logger.log("search_documents", f"query={query!r} -> {len(documents)} document(s)")
        return {
            "documents": [
                {"id": document.id, "title": document.title, "file_type": document.file_type}
                for document in documents
            ]
        }

    def get_source_chunk(self, chunk_id: int) -> dict:
        chunk = self.repository.get_source_chunk(chunk_id)
        self.logger.log(
            "get_source_chunk", f"chunk_id={chunk_id} -> {'found' if chunk else 'not found'}"
        )
        if chunk is None:
            raise ValueError(f"Source chunk {chunk_id} not found.")
        return {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "page_number": chunk.page_number,
            "text": chunk.text,
        }

    def get_user_mastery(self, concept_id: int) -> dict:
        record = self.mastery.get_record(concept_id)
        estimate = self.mastery.get_estimate(concept_id)
        evidence = record.evidence_count if record else 0
        self.logger.log(
            "get_user_mastery",
            f"concept_id={concept_id} -> mastery={estimate}, evidence={evidence}",
        )
        return {
            "concept_id": concept_id,
            "estimated_mastery": estimate,
            "evidence_count": evidence,
            "correct_count": record.correct_count if record else 0,
            "incorrect_count": record.incorrect_count if record else 0,
            "status": self.gap_detector.classify(estimate, evidence),
        }

    # -- Learning tools -------------------------------------------------------

    def generate_assessment(self, concept_id: int, difficulty: int | None = None) -> dict:
        attempt = self.assessment.generate(concept_id, difficulty)
        concept = self.repository.get_concept(concept_id)
        self.logger.log(
            "generate_assessment",
            f"concept_id={concept_id}, difficulty={attempt.difficulty} -> attempt_id={attempt.id}",
        )
        return {
            "attempt_id": attempt.id,
            "concept_id": concept_id,
            "concept_name": concept.name if concept else "",
            "question": attempt.question,
            "question_type": attempt.question_type,
            "difficulty": attempt.difficulty,
        }

    def record_assessment(self, attempt_id: int, user_answer: str) -> dict:
        attempt, record, evaluation = self.assessment.submit(attempt_id, user_answer)
        self.logger.log(
            "record_assessment",
            f"attempt_id={attempt_id} -> correct={evaluation.correct}, score={evaluation.score}, "
            f"mastery={record.estimated_mastery}",
        )
        return {
            "attempt_id": attempt_id,
            "concept_id": attempt.concept_id,
            "correct": evaluation.correct,
            "score": evaluation.score,
            "reasoning": evaluation.reasoning,
            "identified_mistakes": evaluation.identified_mistakes,
            "estimated_mastery": record.estimated_mastery,
            "evidence_count": record.evidence_count,
        }

    def recommend_next_topic(self, target_concept_id: int | None = None, limit: int = 3) -> dict:
        topics = self.recommender.recommend(target_concept_id, limit)
        self.logger.log(
            "recommend_next_topic",
            f"target={target_concept_id} -> {[topic.concept.name for topic in topics]}",
        )
        return {
            "topics": [
                {
                    "concept": concept_dict(topic.concept),
                    "status": topic.status,
                    "mastery": topic.mastery,
                    "evidence_count": topic.evidence_count,
                    "reason": topic.reason,
                }
                for topic in topics
            ]
        }

    # -- Write tools ------------------------------------------------------------

    def create_concept(self, name: str, description: str = "") -> dict:
        concept = self.repository.create_concept(name=name, description=description)
        self.logger.log("create_concept", f"name={concept.name!r} -> concept_id={concept.id}")
        return concept_dict(concept)

    def update_concept(self, concept_id: int, description: str) -> dict:
        concept = self.repository.update_concept(concept_id, description=description)
        self.logger.log("update_concept", f"concept_id={concept_id}")
        if concept is None:
            raise ValueError(f"Concept {concept_id} not found.")
        return concept_dict(concept)

    def create_relationship(
        self,
        source: str,
        target: str,
        relation_type: str,
        confidence: float = 0.7,
    ) -> dict:
        result = RelationshipService(self.repository, self.resolver).create(
            source=source, target=target, relation_type=relation_type, confidence=confidence
        )
        self.logger.log(
            "create_relationship",
            f"{source} --{result['relation_type']}--> {target} (created={result['created']})",
        )
        return result
