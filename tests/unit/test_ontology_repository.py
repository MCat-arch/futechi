import yaml

from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    DEFAULT_SYNONYM_PATH,
    OntologyRepository,
    normalize_term,
    resolve_term,
)

ONTOLOGY = OntologyRepository()


def test_every_synonym_key_is_a_canonical_visual_feature() -> None:
    synonyms = yaml.safe_load(DEFAULT_SYNONYM_PATH.read_text(encoding="utf-8"))
    unknown = [key for key in synonyms if not ONTOLOGY.is_valid_visual_feature(key)]
    assert unknown == []


def test_no_alias_points_to_two_different_canonical_terms() -> None:
    owners: dict[str, set[str]] = {}
    for canonical, aliases in ONTOLOGY.alias_map().items():
        for term in [canonical, *aliases]:
            owners.setdefault(normalize_term(term), set()).add(canonical)
    ambiguous = {term: names for term, names in owners.items() if len(names) > 1}
    assert ambiguous == {}


def test_resolve_visual_feature_exact_alias_and_fuzzy() -> None:
    assert ONTOLOGY.resolve_visual_feature("LOWERED_HEAD_POSTURE") == "lowered_head_posture"
    assert ONTOLOGY.resolve_visual_feature("Mata Berair") == "watery_foamy_eyes"
    assert ONTOLOGY.resolve_visual_feature("conjunctivitus") is None
    assert ONTOLOGY.resolve_visual_feature("conjunctivitus", fuzzy_cutoff=0.85) == "conjunctivitis"
    assert ONTOLOGY.resolve_visual_feature("sesuatu yang lain", fuzzy_cutoff=0.85) is None


def test_resolve_term_handles_blank_label() -> None:
    assert resolve_term("   ", {"a": []}) is None


def test_visual_feature_catalog_filters_by_target() -> None:
    bird_terms = ONTOLOGY.visual_feature_catalog(["bird"])
    assert bird_terms and all(term.category == "bird" for term in bird_terms)
    assert all(term.description for term in bird_terms)
    all_names = {term.name for term in ONTOLOGY.visual_feature_catalog()}
    assert {"shell_less_egg", "visible_mold_on_feed"} <= all_names


def test_alias_map_can_be_restricted_to_subset() -> None:
    subset = ONTOLOGY.alias_map(["conjunctivitis", "not_a_term"])
    assert list(subset) == ["conjunctivitis"]


def test_symptom_and_environment_vocabulary() -> None:
    assert ONTOLOGY.is_valid_symptom("tracheal_rales")
    assert not ONTOLOGY.is_valid_visual_feature("tracheal_rales")
    for condition in ("temperature_attention", "humidity_attention", "ammonia_attention", "wet_litter"):
        assert ONTOLOGY.is_valid_environment_condition(condition)
