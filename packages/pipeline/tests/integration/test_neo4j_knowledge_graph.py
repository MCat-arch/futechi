"""Integration test: isi graph hasil bootstrap & template retrieval di Neo4j sungguhan."""
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SEED_DIR = (
    Path(__file__).parents[2]
    / "src"
    / "futechi_graphrag"
    / "pipelines"
    / "knowledge_graph"
    / "cypher"
    / "seeds"
)
NODE_PATTERN = re.compile(r'MERGE\s*\(\w+:(\w+)\s*\{id:\s*"([^"]+)"\}\)')
REL_PATTERN = re.compile(r"MERGE\s*\(\w+\)-\[\w*:(\w+)[^\]]*\]->\(\w+\)")


def _seed_text() -> str:
    lines = []
    for path in sorted(SEED_DIR.glob("*.cypher")):
        lines += [
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.strip().startswith("//")
        ]
    return "\n".join(lines)


def _expected_counts() -> tuple[dict[str, int], dict[str, int]]:
    text = _seed_text()
    nodes: dict[str, set[str]] = {}
    for label, node_id in NODE_PATTERN.findall(text):
        nodes.setdefault(label, set()).add(node_id)
    relationships: dict[str, int] = {}
    for rel_type in REL_PATTERN.findall(text):
        relationships[rel_type] = relationships.get(rel_type, 0) + 1
    return {label: len(ids) for label, ids in nodes.items()}, relationships


def test_graph_counts_match_seed_files(neo4j_session) -> None:
    expected_nodes, expected_relationships = _expected_counts()

    actual_nodes = {
        record["label"]: record["count"]
        for record in neo4j_session.run(
            "MATCH (n) UNWIND labels(n) AS label WITH label, count(*) AS count "
            "WHERE label <> '_SchemaMigration' RETURN label, count"
        )
    }
    actual_relationships = {
        record["type"]: record["count"]
        for record in neo4j_session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count")
    }

    assert actual_nodes == expected_nodes, "Jalankan: python scripts/bootstrap_neo4j.py --reset --yes"
    assert actual_relationships == expected_relationships


def test_canonical_vocabulary_exists_in_graph(neo4j_session, ontology_repository) -> None:
    graph_names = {record["name"] for record in neo4j_session.run("MATCH (n:VisualFeature) RETURN n.name AS name")}
    assert graph_names == {term.name for term in ontology_repository.visual_feature_catalog()}


def test_every_disease_has_inspection_mitigation_and_treatment(neo4j_session) -> None:
    missing = [
        record["id"]
        for record in neo4j_session.run(
            "MATCH (d:Disease) "
            "WHERE NOT (d)-[:REQUIRES_INSPECTION]->() OR NOT (d)-[:MITIGATED_BY]->() "
            "OR NOT (d)-[:TREATED_WITH]->() RETURN d.id AS id"
        )
    ]
    assert missing == []


def test_every_visual_feature_and_symptom_is_linked(neo4j_session) -> None:
    orphans = neo4j_session.run(
        "MATCH (n) WHERE (n:VisualFeature OR n:Symptom) AND NOT ()-->(n) RETURN count(n) AS c"
    ).single()["c"]
    assert orphans == 0


def test_retrieval_returns_respiratory_differential_candidates(disease_repository) -> None:
    context = disease_repository.retrieve_context(
        visual_features=["conjunctivitis", "nasal_discharge"],
        environment_conditions=["ammonia_attention"],
    )
    by_id = {candidate.disease_id: candidate for candidate in context.candidates}

    assert {"DIS-001", "DIS-002", "DIS-003", "DIS-008"} <= set(by_id)
    # kandidat dengan 2 fitur cocok diurutkan lebih dulu
    match_counts = [len(c.matched_visual_features) for c in context.candidates]
    assert match_counts == sorted(match_counts, reverse=True)

    crd = by_id["DIS-001"]
    assert crd.condition_type == "infectious_bacterial"
    assert [env.name for env in crd.matched_environment] == ["ammonia_attention"]
    assert [symptom.name for symptom in crd.related_symptoms] == ["tracheal_rales"]
    assert crd.medical_treatments and crd.medical_treatments[0].name.startswith("[DUMMY]")
    assert crd.diagnostic_note


def test_retrieval_respects_excluded_disease_ids(disease_repository) -> None:
    context = disease_repository.retrieve_context(
        visual_features=["conjunctivitis"], environment_conditions=[], excluded_disease_ids=["DIS-001"]
    )
    ids = [candidate.disease_id for candidate in context.candidates]
    assert ids and "DIS-001" not in ids


def test_cyanotic_comb_surfaces_notifiable_hpai_and_heat_stress(disease_repository) -> None:
    context = disease_repository.retrieve_context(["cyanotic_comb_wattle"], ["temperature_attention"])
    by_id = {candidate.disease_id: candidate for candidate in context.candidates}

    assert by_id["DIS-009"].notifiable is True
    assert by_id["DIS-017"].notifiable is False
    assert [env.name for env in by_id["DIS-017"].matched_environment] == ["temperature_attention"]


def test_retrieval_without_match_returns_empty_context(disease_repository) -> None:
    assert disease_repository.retrieve_context(["uneven_flock_growth"], [], ["DIS-016"]).is_empty()


def test_unknown_term_is_rejected_before_query(disease_repository) -> None:
    with pytest.raises(ValueError):
        disease_repository.retrieve_context(["head down"], [])
