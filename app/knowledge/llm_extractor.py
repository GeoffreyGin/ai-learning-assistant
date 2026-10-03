"""LLM-backed concept and relationship extraction (structured, validated output).

Replaces the deterministic LocalConceptExtractor when an LLM provider is configured.
The output schema is the same, so persistence and API contracts do not change.
"""

from __future__ import annotations

from app.knowledge.extractor import ExtractionResult
from app.llm.provider import LLMMessage, LLMProvider

EXTRACTION_SYSTEM_PROMPT = """\
You extract structured knowledge from an excerpt of a learning document.

Rules:
- Concepts: key technical terms, theorems, models, and methods a learner must understand.
  Use the canonical form of the name (e.g. "Ito's Lemma", not "ito lemma"). Write a short
  description based ONLY on what the text says. Do not invent concepts the text does not support.
- Relationships: only relationships the text itself supports. Use these types:
  PREREQUISITE_OF (source is required knowledge to understand target),
  RELATED_TO, PART_OF, EXAMPLE_OF, DERIVED_FROM, CONTRADICTS.
- Every relationship endpoint must be a concept name: either one from your concepts list,
  or a concept the text clearly presupposes the reader should know (such as a prerequisite
  named in passing).
- Give each relationship a confidence between 0 and 1.
- Return at most 20 concepts.
"""


class LLMConceptExtractor:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def extract(self, text: str) -> ExtractionResult:
        return self.llm.structured_generate(
            [
                LLMMessage(role="system", content=EXTRACTION_SYSTEM_PROMPT),
                LLMMessage(role="user", content=f"Source excerpt:\n\n{text}"),
            ],
            schema=ExtractionResult,
            max_tokens=4096,
            temperature=0.1,
        )
