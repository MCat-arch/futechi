from pathlib import Path

import pytest

from futechi_graphrag.domain.value_objects.graph_context import GraphContext
from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.pipelines.module_b_graph_retrieval.boundary_check import (
    is_context_empty,
    retry_with_fuzzy_expansion,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval.query_params_builder import (
    build_params,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval.retriever import retrieve


class FakeOntology:
    def is_valid_visual_feature(self, name: str) -> bool:
        return name == "lowered_head_posture"

    def is_valid_environment_condition(self, name: str) -> bool:
        return name == "humidity_attention"


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict[str, list[str]]] = []

    def retrieve_context(self, **params: list[str]) -> list[GraphContext]:
        self.calls.append(params)
        return []


def test_builder_filters_confidence_and_deduplicates() -> None:
    params = build_params(
        [
            VisualFeatureObservation("lowered_head_posture", 0.9),
            VisualFeatureObservation("lowered_head_posture", 0.8),
            VisualFeatureObservation("lowered_head_posture", 0.5),
        ],
        ["humidity_attention", "humidity_attention"],
        ontology_repository=FakeOntology(),
    )
    assert params == {
        "visual_features": ["lowered_head_posture"],
        "environment_conditions": ["humidity_attention"],
    }


def test_builder_rejects_unknown_canonical_terms() -> None:
    with pytest.raises(ValueError):
        build_params(
            [VisualFeatureObservation("unknown", 1.0)],
            [],
            ontology_repository=FakeOntology(),
        )


def test_retriever_delegates_to_repository() -> None:
    repository = FakeRepository()
    assert retrieve({"visual_features": [], "environment_conditions": []}, repository) == []
    assert repository.calls == [{"visual_features": [], "environment_conditions": []}]


def test_boundary_retry_expands_known_synonyms(tmp_path: Path) -> None:
    synonym_file = tmp_path / "synonyms.yaml"
    synonym_file.write_text(
        "lowered_head_posture:\n  - head down\n", encoding="utf-8"
    )
    repository = FakeRepository()
    assert retry_with_fuzzy_expansion(
        {"visual_features": ["head down"], "environment_conditions": []},
        repository,
        synonym_file,
    ) == []
    assert repository.calls[0]["visual_features"] == [
        "lowered_head_posture",
    ]


def test_empty_context_is_detected() -> None:
    assert is_context_empty(None)
    assert is_context_empty([])
