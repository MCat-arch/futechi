from pathlib import Path

import pytest

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval.boundary_check import (
    is_context_empty,
    retry_with_synonym_remap,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval.query_params_builder import (
    build_params,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval.retriever import retrieve

ONTOLOGY = OntologyRepository()
TEMPLATE_PATH = (
    Path(__file__).parents[2]
    / "src"
    / "futechi_graphrag"
    / "pipelines"
    / "knowledge_graph"
    / "cypher"
    / "templates"
    / "retrieve_disease_context.cypher"
)


class FakeRepository:
    def __init__(self, context: GraphContext | None = None) -> None:
        self.calls: list[dict] = []
        self.context = context or GraphContext(candidates=[])

    def retrieve_context(self, **params) -> GraphContext:
        self.calls.append(params)
        return self.context


class FakeRunner:
    def __init__(self, records: list[dict]) -> None:
        self.records = records
        self.calls: list[tuple[str, dict]] = []

    def run_read_query(self, query: str, params: dict) -> list[dict]:
        self.calls.append((query, params))
        return self.records


def _record(**overrides) -> dict:
    record = {
        "disease_id": "DIS-001",
        "disease_name": "CRD (Mycoplasma gallisepticum)",
        "disease_desc": "desc",
        "condition_type": "infectious_bacterial",
        "base_severity": "medium",
        "notifiable": False,
        "validation_note": "validasi",
        "diagnostic_note": "diagnostik",
        "matched_visual_features": [
            {
                "name": "conjunctivitis",
                "specificity": "low",
                "onset_stage": None,
                "mechanism": None,
                "clinical_note": "catatan",
            }
        ],
        "related_symptoms": [
            {"name": None, "specificity": None, "onset_stage": None, "mechanism": None, "clinical_note": None}
        ],
        "matched_environment": [{"name": None, "strength": None, "note": None}],
        "inspection_actions": [
            {"name": "observe_breathing", "instruction": "dengar", "performed_by": "farmer"}
        ],
        "mitigation_actions": [],
        "medical_treatments": [],
    }
    record.update(overrides)
    return record


# ----------------------------------------------------------------------
# query_params_builder / retriever
# ----------------------------------------------------------------------
def test_builder_filters_confidence_deduplicates_and_keeps_exclusions() -> None:
    params = build_params(
        [
            VisualFeatureObservation("conjunctivitis", 0.9),
            VisualFeatureObservation("conjunctivitis", 0.8),
            VisualFeatureObservation("nasal_discharge", 0.5),
        ],
        ["humidity_attention", "humidity_attention"],
        ontology_repository=ONTOLOGY,
        excluded_disease_ids=["DIS-009", "DIS-009"],
    )
    assert params == {
        "visual_features": ["conjunctivitis"],
        "environment_conditions": ["humidity_attention"],
        "excluded_disease_ids": ["DIS-009"],
    }


def test_builder_accepts_all_sensor_conditions() -> None:
    params = build_params(
        [VisualFeatureObservation("open_mouth_breathing", 0.9)],
        ["temperature_attention", "humidity_attention", "ammonia_attention"],
        ontology_repository=ONTOLOGY,
    )
    assert params["environment_conditions"] == [
        "temperature_attention",
        "humidity_attention",
        "ammonia_attention",
    ]


def test_builder_rejects_unknown_canonical_terms() -> None:
    with pytest.raises(ValueError):
        build_params([VisualFeatureObservation("unknown", 1.0)], [], ontology_repository=ONTOLOGY)


def test_retriever_delegates_to_repository_and_returns_graph_context() -> None:
    repository = FakeRepository()
    result = retrieve(
        {"visual_features": ["conjunctivitis"], "environment_conditions": [], "excluded_disease_ids": []},
        repository,
    )
    assert isinstance(result, GraphContext) and result.is_empty()
    assert repository.calls == [
        {"visual_features": ["conjunctivitis"], "environment_conditions": [], "excluded_disease_ids": []}
    ]


def test_retriever_rejects_non_list_params() -> None:
    with pytest.raises(TypeError):
        retrieve({"visual_features": "conjunctivitis"}, FakeRepository())


# ----------------------------------------------------------------------
# boundary_check
# ----------------------------------------------------------------------
def test_empty_context_is_detected() -> None:
    assert is_context_empty(None)
    assert is_context_empty(GraphContext(candidates=[]))


def test_retry_remaps_unmapped_labels_and_queries_once_with_new_features() -> None:
    repository = FakeRepository()
    outcome = retry_with_synonym_remap(
        {"visual_features": ["nasal_discharge"], "environment_conditions": ["humidity_attention"]},
        ["conjunctivitus", "mata berair", "nasal discharge"],
        repository,
        ontology_repository=ONTOLOGY,
    )

    assert outcome.executed is True
    assert outcome.added_visual_features == ["conjunctivitis", "watery_foamy_eyes"]
    assert repository.calls == [
        {
            "visual_features": ["nasal_discharge", "conjunctivitis", "watery_foamy_eyes"],
            "environment_conditions": ["humidity_attention"],
            "excluded_disease_ids": [],
        }
    ]


def test_retry_skips_query_when_nothing_new_can_be_mapped() -> None:
    repository = FakeRepository()
    outcome = retry_with_synonym_remap(
        {"visual_features": ["conjunctivitis"], "environment_conditions": []},
        ["completely unrelated observation"],
        repository,
        ontology_repository=ONTOLOGY,
    )
    assert outcome.executed is False
    assert outcome.graph_context.is_empty()
    assert repository.calls == []


# ----------------------------------------------------------------------
# DiseaseRepository + template
# ----------------------------------------------------------------------
def test_repository_maps_records_to_single_graph_context_type() -> None:
    runner = FakeRunner([_record()])
    repository = DiseaseRepository(runner, ontology_repository=ONTOLOGY, query_path=TEMPLATE_PATH)

    context = repository.retrieve_context(
        visual_features=["conjunctivitis"],
        environment_conditions=["humidity_attention"],
        excluded_disease_ids=["DIS-009"],
    )

    assert isinstance(context, GraphContext)
    candidate = context.candidates[0]
    assert candidate.condition_type == "infectious_bacterial"
    assert candidate.diagnostic_note == "diagnostik"
    assert candidate.matched_visual_features[0].clinical_note == "catatan"
    assert candidate.related_symptoms == []  # entri OPTIONAL MATCH kosong dibuang
    assert candidate.matched_environment == []
    assert candidate.inspection_actions[0].performed_by == "farmer"
    assert runner.calls[0][1] == {
        "visual_features": ["conjunctivitis"],
        "environment_conditions": ["humidity_attention"],
        "excluded_disease_ids": ["DIS-009"],
    }


def test_repository_skips_query_without_visual_features() -> None:
    runner = FakeRunner([_record()])
    repository = DiseaseRepository(runner, ontology_repository=ONTOLOGY, query_path=TEMPLATE_PATH)
    assert repository.retrieve_context([], ["humidity_attention"]).is_empty()
    assert runner.calls == []


def test_repository_rejects_unknown_terms_before_querying() -> None:
    runner = FakeRunner([])
    repository = DiseaseRepository(runner, ontology_repository=ONTOLOGY, query_path=TEMPLATE_PATH)
    with pytest.raises(ValueError):
        repository.retrieve_context(["head down"], [])
    assert runner.calls == []


def test_template_returns_every_column_used_by_dto_mapper() -> None:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    for column in _record():
        assert f"AS {column}" in template
    assert "$excluded_disease_ids" in template
    assert "clinical_note: hf.clinical_note" in template
