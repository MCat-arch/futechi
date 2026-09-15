import pytest

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.canonical_mapper import (
    map_to_canonical_terms,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.confidence_filter import (
    filter_by_confidence,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.frame_aggregator import (
    aggregate_candidates,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.mapping_validator import (
    validate_mapping,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    EXTRACTION_SYSTEM_PROMPT,
    ExtractedFeature,
    FrameExtractionResponse,
    OtherObservation,
    extract_frame_features,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.pipeline import (
    run_module_semantic_mapping_pipeline,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.sensor_normalizer import (
    normalize_environment,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.types import RawVisualCandidate

ONTOLOGY = OntologyRepository()


class FakeMLLMClient:
    def __init__(self, responses: list[FrameExtractionResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def generate_structured_with_images(self, system_prompt, user_prompt, images, schema):
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, "images": list(images), "schema": schema}
        )
        return self.responses.pop(0)


def _frame(features=(), others=(), usable=True, reason=None) -> FrameExtractionResponse:
    return FrameExtractionResponse(
        image_usable=usable,
        unusable_reason=reason,
        features=[ExtractedFeature(name=n, confidence=c) for n, c in features],
        other_observations=[OtherObservation(label=l, confidence=c) for l, c in others],
    )


# ----------------------------------------------------------------------
# mllm_extractor
# ----------------------------------------------------------------------
def test_extract_frame_features_calls_mllm_per_frame_with_closed_vocabulary() -> None:
    vocabulary = ONTOLOGY.visual_feature_catalog(["bird"])
    client = FakeMLLMClient(
        [
            _frame(features=[("conjunctivitis", 0.9)], others=[("red spots", 0.7)]),
            _frame(usable=False, reason="terlalu buram"),
        ]
    )

    result = extract_frame_features([b"img-0", b"img-1"], client, vocabulary)

    assert len(client.calls) == 2
    assert client.calls[0]["images"] == [b"img-0"]
    assert client.calls[0]["system"] == EXTRACTION_SYSTEM_PROMPT
    assert client.calls[0]["schema"] is FrameExtractionResponse
    assert "- conjunctivitis:" in client.calls[0]["user"]
    assert "shell_less_egg" not in client.calls[0]["user"]

    assert result.frames_total == 2
    assert result.frames_usable == 1
    assert result.notes == ["frame-1 tidak dapat dinilai: terlalu buram"]
    assert result.candidates == [
        RawVisualCandidate("conjunctivitis", 0.9, "frame-0"),
        RawVisualCandidate("red spots", 0.7, "frame-0"),
    ]


def test_extraction_prompt_is_conservative_for_low_capture_quality() -> None:
    client = FakeMLLMClient([_frame()])
    extract_frame_features([b"img"], client, ONTOLOGY.visual_feature_catalog(["bird"]), "low")
    assert "konservatif" in client.calls[0]["user"]


def test_extract_frame_features_requires_vocabulary() -> None:
    with pytest.raises(ValueError):
        extract_frame_features([b"img"], FakeMLLMClient([]), [])


# ----------------------------------------------------------------------
# canonical_mapper / aggregator / filter / validator
# ----------------------------------------------------------------------
def test_map_to_canonical_terms_resolves_names_and_normalized_aliases() -> None:
    alias_map = {
        "lowered_head_posture": ["head down", "drooping head"],
        "conjunctivitis": [],
    }
    candidates = [
        RawVisualCandidate("Head-Down", 0.9, "frame-0"),
        RawVisualCandidate("CONJUNCTIVITIS", 0.7, "frame-0"),
        RawVisualCandidate("weird posture", 0.5, "frame-1"),
    ]

    mapped, unmapped = map_to_canonical_terms(candidates, alias_map)

    assert mapped == [
        RawVisualCandidate("lowered_head_posture", 0.9, "frame-0"),
        RawVisualCandidate("conjunctivitis", 0.7, "frame-0"),
    ]
    assert unmapped == [RawVisualCandidate("weird posture", 0.5, "frame-1")]


def test_aggregate_candidates_keeps_majority_labels_with_mean_confidence() -> None:
    candidates = [
        RawVisualCandidate("conjunctivitis", 0.9, "frame-0"),
        RawVisualCandidate("conjunctivitis", 0.7, "frame-1"),
        RawVisualCandidate("nasal_discharge", 0.8, "frame-2"),
    ]

    aggregated = aggregate_candidates(candidates, frames_usable=3)

    assert len(aggregated) == 1
    assert aggregated[0].label == "conjunctivitis"
    assert aggregated[0].confidence == pytest.approx(0.8)
    assert aggregated[0].frame_support == 2


def test_aggregate_candidates_counts_duplicate_label_in_same_frame_once() -> None:
    candidates = [
        RawVisualCandidate("lowered_head_posture", 0.6, "frame-0"),
        RawVisualCandidate("lowered_head_posture", 0.9, "frame-0"),
    ]
    assert aggregate_candidates(candidates, frames_usable=3) == []
    kept = aggregate_candidates(candidates, frames_usable=1)
    assert kept[0].confidence == pytest.approx(0.9)
    assert kept[0].frame_support == 1


def test_aggregate_candidates_without_usable_frames_returns_empty() -> None:
    assert aggregate_candidates([RawVisualCandidate("x", 1.0, "frame-0")], frames_usable=0) == []


def test_filter_by_confidence_keeps_only_valid_candidates() -> None:
    candidates = [
        RawVisualCandidate("head down", 0.91, "frame_a"),
        RawVisualCandidate("ruffled feathers", 0.59, "frame_a"),
    ]
    assert filter_by_confidence(candidates, threshold=0.6) == [
        RawVisualCandidate("head down", 0.91, "frame_a")
    ]


def test_validate_mapping_flags_excess_unmapped_ratio() -> None:
    assert validate_mapping(mapped_count=1, unmapped_count=2) == (True, 2 / 3)
    assert validate_mapping(mapped_count=2, unmapped_count=1) == (False, 1 / 3)


def test_validate_mapping_flags_when_no_feature_is_mapped() -> None:
    assert validate_mapping(mapped_count=0, unmapped_count=0) == (True, 0.0)


def test_normalize_environment_detects_attention_conditions() -> None:
    conditions = normalize_environment(temperature_c=31.5, humidity_percent=80, ammonia_ppm=25)
    assert conditions == ["temperature_attention", "humidity_attention", "ammonia_attention"]


# ----------------------------------------------------------------------
# pipeline
# ----------------------------------------------------------------------
def test_pipeline_maps_aggregates_and_filters_features() -> None:
    client = FakeMLLMClient(
        [
            _frame(
                features=[("conjunctivitis", 0.9), ("nasal_discharge", 0.8)],
                others=[("weird comb spots", 0.7)],
            ),
            _frame(features=[("conjunctivitis", 0.8)], others=[("head down", 0.7)]),
            _frame(
                features=[
                    ("conjunctivitis", 0.7),
                    ("nasal_discharge", 0.6),
                    ("lowered_head_posture", 0.8),
                ]
            ),
        ]
    )

    result = run_module_semantic_mapping_pipeline(
        frames=[b"a", b"b", b"c"],
        mllm_client=client,
        raw_environment={"temperature_c": 31.5, "humidity_percent": None, "ammonia_ppm": 25},
        ontology_repository=ONTOLOGY,
    )

    assert [f.name for f in result.visual_features] == [
        "conjunctivitis",
        "nasal_discharge",
        "lowered_head_posture",
    ]
    assert result.visual_features[0].confidence == pytest.approx(0.8)
    assert result.visual_features[1].confidence == pytest.approx(0.7)
    assert result.visual_features[2].confidence == pytest.approx(0.75)
    assert result.environment_conditions == ["temperature_attention", "ammonia_attention"]
    assert result.unmapped_visuals == []
    assert result.manual_review_required is False
    assert (result.frames_total, result.frames_usable) == (3, 3)


def test_pipeline_treats_features_outside_prompted_targets_as_unmapped() -> None:
    client = FakeMLLMClient(
        [
            _frame(features=[("conjunctivitis", 0.9), ("shell_less_egg", 0.9)]),
            _frame(features=[("shell_less_egg", 0.8)], others=[("Odd Beak Crust", 0.8)]),
            _frame(others=[("odd beak crust", 0.9)]),
        ]
    )

    result = run_module_semantic_mapping_pipeline(
        frames=[b"a", b"b", b"c"], mllm_client=client, ontology_repository=ONTOLOGY
    )

    assert result.visual_features == []
    assert result.unmapped_visuals == ["shell less egg", "odd beak crust"]
    assert result.manual_review_required is True
    assert result.environment_conditions == []


def test_pipeline_requires_manual_review_when_no_frame_is_usable() -> None:
    client = FakeMLLMClient([_frame(usable=False, reason="gelap")] * 2)

    result = run_module_semantic_mapping_pipeline(
        frames=[b"a", b"b"], mllm_client=client, ontology_repository=ONTOLOGY
    )

    assert result.manual_review_required is True
    assert result.frames_usable == 0
    assert "Tidak ada frame yang dapat dinilai MLLM." in result.notes


def test_pipeline_requires_manual_review_when_no_abnormal_feature_found() -> None:
    client = FakeMLLMClient([_frame(), _frame(), _frame()])

    result = run_module_semantic_mapping_pipeline(
        frames=[b"a", b"b", b"c"], mllm_client=client, ontology_repository=ONTOLOGY
    )

    assert result.visual_features == [] and result.unmapped_visuals == []
    assert result.manual_review_required is True


def test_pipeline_output_uses_domain_observation_type() -> None:
    client = FakeMLLMClient([_frame(features=[("pale_comb", 0.9)])])
    result = run_module_semantic_mapping_pipeline(
        frames=[b"a"], mllm_client=client, ontology_repository=ONTOLOGY
    )
    assert result.visual_features == [VisualFeatureObservation("pale_comb", 0.9)]
