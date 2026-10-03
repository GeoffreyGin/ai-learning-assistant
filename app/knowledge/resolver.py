"""Concept resolution: decide whether a newly extracted name matches an existing concept (spec §12).

Exact normalized matches resolve immediately. Near matches go through a fuzzy similarity
check and, when an LLM is available, a confirmation call. This keeps duplicates such as
"Ito Lemma" / "Itô's lemma" merged while keeping "Black-Scholes Model" / "Black-Scholes
PDE" separate.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from app.db.models import Concept, SourceChunk
from app.db.repositories import KnowledgeRepository, normalize_concept_name
from app.llm.provider import LLMError, LLMMessage, LLMProvider

FUZZY_THRESHOLD = 0.85  # below this ratio, names are considered distinct concepts
AUTO_MERGE_THRESHOLD = 0.95  # at or above this ratio, merge without an LLM check
MAX_LLM_CHECKS_PER_INGESTION = 20

_LEADING_STOPWORDS = frozenset({"the", "a", "an"})


def _is_word_subsequence(short: list[str], long: list[str]) -> bool:
    """True when `short` is a contiguous run of whole words inside `long`."""
    if len(short) > len(long):
        return False
    return any(
        long[start : start + len(short)] == short for start in range(len(long) - len(short) + 1)
    )


class SameConceptVerdict(BaseModel):
    same_concept: bool = Field(description="Whether the two names refer to the same concept.")
    reasoning: str = Field(default="")


class ConceptResolver:
    def __init__(self, repository: KnowledgeRepository, llm: LLMProvider | None = None) -> None:
        self.repository = repository
        self.llm = llm
        self.llm_checks_left = MAX_LLM_CHECKS_PER_INGESTION

    def resolve(
        self,
        name: str,
        description: str = "",
        source_chunk: SourceChunk | None = None,
    ) -> tuple[Concept, bool]:
        """Return (concept, created): an existing concept on match, else a new one."""
        normalized = normalize_concept_name(name)
        if not normalized:
            raise ValueError("Concept name must contain letters or numbers.")

        exact = self.repository.get_concept_by_normalized(normalized)
        if exact is not None:
            return self._merge(exact, description, source_chunk), False

        candidates = self._fuzzy_candidates(normalized)
        if not candidates:
            created = self.repository.create_concept(
                name=name, description=description, source_chunk=source_chunk
            )
            return created, True

        best_concept, best_ratio = candidates[0]
        if best_ratio < AUTO_MERGE_THRESHOLD:
            # Borderline match. Ask the LLM when available; without one (or on LLM
            # failure), stay conservative and keep the concepts separate — a duplicate
            # is cheaper to fix than wrongly merging distinct concepts.
            if self.llm is not None and self.llm_checks_left > 0:
                self.llm_checks_left -= 1
                try:
                    if self._llm_confirms(best_concept, name):
                        return self._merge(best_concept, description, source_chunk), False
                except LLMError:
                    pass
            created = self.repository.create_concept(
                name=name, description=description, source_chunk=source_chunk
            )
            return created, True
        return self._merge(best_concept, description, source_chunk), False

    def _merge(
        self, concept: Concept, description: str, source_chunk: SourceChunk | None
    ) -> Concept:
        if description.strip() and not concept.description:
            self.repository.update_concept(concept.id, description=description)
        if source_chunk is not None:
            self.repository.attach_source_chunk(concept, source_chunk)
        return concept

    def _fuzzy_candidates(self, normalized: str) -> list[tuple[Concept, float]]:
        """Concepts sharing the first meaningful word, scored by normalized-name similarity.

        When one name is a whole-word prefix of the other (e.g. "Black-Scholes" vs
        "Black-Scholes Model"), the pair scores in the LLM-check band so a configured
        LLM can decide whether it is an abbreviation of the same concept.
        """
        first_word = self._first_word(normalized)
        target_words = normalized.split()
        scored: list[tuple[Concept, float]] = []
        for concept in self.repository.list_concepts():
            candidate_words = concept.normalized_name.split()
            if self._first_word(concept.normalized_name) != first_word:
                continue
            if _is_word_subsequence(candidate_words, target_words) or _is_word_subsequence(
                target_words, candidate_words
            ):
                ratio = 0.9
            else:
                ratio = SequenceMatcher(None, concept.normalized_name, normalized).ratio()
            if ratio >= FUZZY_THRESHOLD:
                scored.append((concept, ratio))
        return sorted(scored, key=lambda item: -item[1])

    def _llm_confirms(self, existing: Concept, new_name: str) -> bool:
        verdict = self.llm.structured_generate(
            [
                LLMMessage(
                    role="system",
                    content=(
                        "Decide whether two names refer to the same concept. Same concept: "
                        "spelling variants, apostrophes, plural forms, or minor word-order changes "
                        "(e.g. 'Ito Lemma' and \"Itô's lemma\"). Different concepts: a genuinely "
                        "different object (e.g. 'Black-Scholes Model' and 'Black-Scholes PDE')."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=f"Existing concept: {existing.name!r}\nNew name: {new_name!r}",
                ),
            ],
            schema=SameConceptVerdict,
            max_tokens=200,
            temperature=0.0,
        )
        return verdict.same_concept

    @staticmethod
    def _first_word(normalized: str) -> str:
        for word in normalized.split():
            if word not in _LEADING_STOPWORDS:
                return word
        return normalized
