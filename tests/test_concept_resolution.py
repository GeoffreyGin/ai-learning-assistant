"""Concept resolution tests (spec §12, §26): merge duplicates, keep near-duplicates apart."""

from app.db.repositories import KnowledgeRepository, normalize_concept_name
from app.knowledge.resolver import ConceptResolver, SameConceptVerdict


def test_normalize_concept_name_merges_ito_spellings() -> None:
    assert normalize_concept_name("Ito Lemma") == normalize_concept_name("Itô's lemma")


def test_normalize_concept_name_keeps_distinct_concepts_distinct() -> None:
    assert normalize_concept_name("Black-Scholes Model") != normalize_concept_name(
        "Black-Scholes PDE"
    )


def test_resolver_merges_spelling_variants(session_factory) -> None:
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository)
        first, created = resolver.resolve("Black-Scholes Model", "An option pricing model.")
        session.commit()
        second, created_second = resolver.resolve("Black Scholes model", "Another description.")
        assert created is True and created_second is False
        assert second.id == first.id
        # Existing description wins.
        assert second.description == "An option pricing model."


def test_resolver_keeps_near_duplicates_separate(session_factory) -> None:
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository)
        model, _ = resolver.resolve("Black-Scholes Model")
        session.commit()
        pde, created = resolver.resolve("Black-Scholes PDE")
        assert created is True
        assert pde.id != model.id


def test_resolver_uses_llm_for_borderline_matches(session_factory, fake_llm) -> None:
    fake_llm.structured[SameConceptVerdict] = SameConceptVerdict(
        same_concept=False, reasoning="A proof is not the theorem itself."
    )
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository, fake_llm)
        existing, _ = resolver.resolve("Central Limit Theorem")
        session.commit()
        kept_separate, created = resolver.resolve("central limit theorem proof")
        assert created is True and kept_separate.id != existing.id


def test_resolver_merges_when_llm_confirms_similar_names(session_factory, fake_llm) -> None:
    fake_llm.structured[SameConceptVerdict] = SameConceptVerdict(
        same_concept=True, reasoning="plural form"
    )
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository, fake_llm)
        existing, _ = resolver.resolve("stochastic process")
        session.commit()
        merged, created = resolver.resolve("stochastic processes")
        assert created is False
        assert merged.id == existing.id


def test_resolver_keeps_concepts_separate_when_llm_fails(session_factory, fake_llm) -> None:
    from app.llm.provider import LLMError

    def raise_error(messages):
        raise LLMError("provider down")

    fake_llm.structured[SameConceptVerdict] = raise_error
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository, fake_llm)
        existing, _ = resolver.resolve("stochastic process")
        session.commit()
        # Conservative fallback: without a working LLM the borderline pair stays separate.
        kept_separate, created = resolver.resolve("stochastic processes")
        assert created is True
        assert kept_separate.id != existing.id


def test_resolver_merges_abbreviation_with_llm_confirmation(session_factory, fake_llm) -> None:
    fake_llm.structured[SameConceptVerdict] = SameConceptVerdict(
        same_concept=True, reasoning="abbreviated form"
    )
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository, fake_llm)
        existing, _ = resolver.resolve("Black-Scholes Model")
        session.commit()
        merged, created = resolver.resolve("Black-Scholes")
        assert created is False
        assert merged.id == existing.id


def test_resolver_keeps_abbreviation_separate_without_llm(session_factory) -> None:
    with session_factory() as session:
        repository = KnowledgeRepository(session)
        resolver = ConceptResolver(repository)
        existing, _ = resolver.resolve("Black-Scholes Model")
        session.commit()
        # Conservative offline: without an LLM to confirm, keep the short form separate.
        short, created = resolver.resolve("Black-Scholes")
        assert created is True
        assert short.id != existing.id


def test_resolver_rejects_blank_names(session_factory) -> None:
    import pytest

    with session_factory() as session:
        with pytest.raises(ValueError):
            ConceptResolver(KnowledgeRepository(session)).resolve("***")
