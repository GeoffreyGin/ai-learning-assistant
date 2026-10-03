"""Knowledge graph traversal tests (spec §26)."""

import pytest

from app.db.repositories import KnowledgeRepository
from app.knowledge.graph import KnowledgeGraph
from app.knowledge.relations import PREREQUISITE_OF


def test_prerequisites_transitive_with_distances(session_factory, seed) -> None:
    seed(["A", "B", "C"], edges=[("A", "B"), ("B", "C")])
    with session_factory() as session:
        graph = KnowledgeGraph(KnowledgeRepository(session))
        prerequisites = graph.prerequisites(concept_id_by_name(session, "C"))
        assert dict(prerequisites) == {
            concept_id_by_name(session, "A"): 2,
            concept_id_by_name(session, "B"): 1,
        }


def test_prerequisites_nearest_first(session_factory, seed) -> None:
    seed(["A", "B", "C"], edges=[("A", "B"), ("B", "C")])
    with session_factory() as session:
        graph = KnowledgeGraph(KnowledgeRepository(session))
        distances = [
            distance for _, distance in graph.prerequisites(concept_id_by_name(session, "C"))
        ]
        assert distances == sorted(distances)


def test_non_prerequisite_edges_are_ignored(session_factory, seed) -> None:
    concepts = seed(["A", "B"])
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        repository.create_relationship(
            source_concept_id=concepts["A"].id,
            target_concept_id=concepts["B"].id,
            relation_type="RELATED_TO",
            confidence=0.5,
        )
        session.commit()
        graph = KnowledgeGraph(repository)
        assert graph.prerequisites(concepts["B"].id) == []
        related = graph.related(concepts["B"].id)
        assert related == [(concepts["A"].id, "RELATED_TO", 0.5)]


def test_prerequisites_survive_cycles(session_factory, seed) -> None:
    concepts = seed(["A", "B"], edges=[("A", "B"), ("B", "A")])
    with session_factory() as session:
        graph = KnowledgeGraph(KnowledgeRepository(session))
        prerequisites = graph.prerequisites(concepts["A"].id)
        assert dict(prerequisites) == {concepts["B"].id: 1}


def test_missing_concept_raises(session_factory) -> None:
    with session_factory() as session:
        with pytest.raises(ValueError):
            KnowledgeGraph(KnowledgeRepository(session)).prerequisites(999)


def test_serialize_produces_nodes_and_edges(session_factory, seed) -> None:
    seed(["A", "B"], edges=[("A", "B")])
    with session_factory() as session:
        payload = KnowledgeGraph(KnowledgeRepository(session)).serialize(mastery={})
        names = {node["name"] for node in payload["nodes"]}
        assert names == {"A", "B"}
        assert payload["edges"] and payload["edges"][0]["type"] == PREREQUISITE_OF


def concept_id_by_name(session, name: str) -> int:
    return KnowledgeRepository(session).get_concept_by_normalized(name.casefold()).id
