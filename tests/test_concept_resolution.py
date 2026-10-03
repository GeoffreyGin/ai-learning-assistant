from app.db.repositories import normalize_concept_name


def test_normalize_concept_name_merges_ito_spellings() -> None:
    assert normalize_concept_name("Ito Lemma") == normalize_concept_name("Itô's lemma")


def test_normalize_concept_name_keeps_distinct_concepts_distinct() -> None:
    assert normalize_concept_name("Black-Scholes Model") != normalize_concept_name("Black-Scholes PDE")
