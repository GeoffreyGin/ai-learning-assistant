"""In-memory graph view over stored relationships, used for traversal (NetworkX, spec §7)."""

from __future__ import annotations

import networkx as nx

from app.db.repositories import KnowledgeRepository
from app.knowledge.relations import PREREQUISITE_OF


class KnowledgeGraph:
    """Built per request from the database, so it never goes stale. Cycle-safe."""

    def __init__(self, repository: KnowledgeRepository) -> None:
        self.repository = repository

    def build(self) -> nx.MultiDiGraph:
        graph = nx.MultiDiGraph()
        for concept in self.repository.list_concepts():
            graph.add_node(concept.id, name=concept.name)
        for relationship in self.repository.list_relationships():
            graph.add_edge(
                relationship.source_concept_id,
                relationship.target_concept_id,
                key=relationship.relation_type,
                type=relationship.relation_type,
                confidence=relationship.confidence,
                evidence_source_id=relationship.evidence_source_id,
            )
        return graph

    def prerequisites(self, concept_id: int) -> list[tuple[int, int]]:
        """All transitive PREREQUISITE_OF ancestors as (concept_id, distance), nearest first."""
        graph = self.build()
        if concept_id not in graph:
            raise ValueError(f"Concept {concept_id} is not in the graph.")
        distances: dict[int, int] = {}
        frontier = [concept_id]
        seen = {concept_id}
        depth = 0
        while frontier:
            depth += 1
            next_frontier: list[int] = []
            for node in frontier:
                for predecessor in graph.predecessors(node):
                    if not graph.has_edge(predecessor, node, key=PREREQUISITE_OF):
                        continue
                    if predecessor not in seen:
                        seen.add(predecessor)
                        distances[predecessor] = depth
                        next_frontier.append(predecessor)
            frontier = next_frontier
        return sorted(distances.items(), key=lambda item: (item[1], item[0]))

    def related(self, concept_id: int) -> list[tuple[int, str, float]]:
        """Neighbors via non-prerequisite relationships: (concept_id, relation_type, confidence)."""
        graph = self.build()
        if concept_id not in graph:
            raise ValueError(f"Concept {concept_id} is not in the graph.")
        results: list[tuple[int, str, float]] = []
        neighbors = sorted(set(graph.predecessors(concept_id)) | set(graph.successors(concept_id)))
        for neighbor in neighbors:
            for source, target in ((concept_id, neighbor), (neighbor, concept_id)):
                if not graph.has_edge(source, target):
                    continue
                for kind, edge in graph[source][target].items():
                    if kind != PREREQUISITE_OF:
                        results.append((neighbor, kind, edge["confidence"]))
        return results

    def serialize(self, mastery: dict[int, float | None] | None = None) -> dict:
        graph = self.build()
        mastery = mastery or {}
        return {
            "nodes": [
                {
                    "id": node,
                    "name": graph.nodes[node]["name"],
                    "mastery": mastery.get(node),
                }
                for node in sorted(graph.nodes)
            ],
            "edges": [
                {
                    "source": source,
                    "target": target,
                    "type": data.get("type"),
                    "confidence": data.get("confidence"),
                    "evidence_source_id": data["evidence_source_id"],
                }
                for source, target, data in graph.edges(data=True)
            ],
        }
