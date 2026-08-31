from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
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
from futechi_graphrag.pipelines.module_a_semantic_mapping.pipeline import (
    run_module_semantic_mapping_pipeline,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.sensor_normalizer import (
    normalize_environment,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.types import RawVisualCandidate
from futechi_graphrag.pipelines.module_a_semantic_mapping.vlm_extractor import (
    extract_raw_features,
)


class FakeVisionClient:
    def analyze(self, frame: str) -> dict:
        if frame == "frame_a":
            return {
                "detections": [
                    {"label": "head down", "confidence": 0.91},
                    {"label": "ruffled feathers", "confidence": 0.72},
                    {"label": "weird posture", "confidence": 0.42},
                ]
            }
        return {
            "detections": [
                {"label": "head down", "confidence": 0.88},
                {"label": "ruffled feathers", "confidence": 0.68},
            ]
        }


def test_extract_raw_features_reads_vlm_output() -> None:
    client = FakeVisionClient()
    features = extract_raw_features(["frame_a", "frame_b"], client)

    assert len(features) == 5
    assert features[0] == RawVisualCandidate(
        label="head down",
        confidence=0.91,
        source_frame="frame_a",
    )


def test_aggregate_candidates_keeps_highest_confidence_per_label() -> None:
    candidates = [
        RawVisualCandidate("head down", 0.7, "frame_a"),
        RawVisualCandidate("head down", 0.9, "frame_b"),
        RawVisualCandidate("ruffled feathers", 0.6, "frame_a"),
    ]

    merged = aggregate_candidates(candidates)

    assert merged == [
        RawVisualCandidate("head down", 0.9, "frame_b"),
        RawVisualCandidate("ruffled feathers", 0.6, "frame_a"),
    ]


def test_filter_by_confidence_keeps_only_valid_candidates() -> None:
    candidates = [
        RawVisualCandidate("head down", 0.91, "frame_a"),
        RawVisualCandidate("ruffled feathers", 0.59, "frame_a"),
    ]

    filtered = filter_by_confidence(candidates, threshold=0.6)

    assert filtered == [RawVisualCandidate("head down", 0.91, "frame_a")]


def test_map_to_canonical_terms_maps_aliases_and_tracks_unmapped() -> None:
    alias_map = {
        "lowered_head_posture": ["head down", "drooping head"],
        "irregular_feather_appearance": ["ruffled feathers"],
    }
    candidates = [
        RawVisualCandidate("head down", 0.9, "frame_a"),
        RawVisualCandidate("ruffled feathers", 0.7, "frame_a"),
        RawVisualCandidate("weird posture", 0.5, "frame_b"),
    ]

    mapped, unmapped = map_to_canonical_terms(candidates, alias_map)

    assert mapped == [
        VisualFeatureObservation("lowered_head_posture", 0.9),
        VisualFeatureObservation("irregular_feather_appearance", 0.7),
    ]
    assert unmapped == ["weird posture"]


def test_normalize_environment_detects_attention_conditions() -> None:
    conditions = normalize_environment(
        temperature_c=31.5,
        humidity_percent=80,
        ammonia_ppm=25,
    )

    assert conditions == [
        "temperature_attention",
        "humidity_attention",
        "ammonia_attention",
    ]


def test_validate_mapping_flags_excess_unmapped_ratio() -> None:
    manual_review, ratio = validate_mapping(mapped_count=1, unmapped_count=2)

    assert manual_review is True
    assert ratio == 2 / 3


def test_run_module_semantic_mapping_pipeline_returns_module_a_payload() -> None:
    alias_map = {
        "lowered_head_posture": ["head down", "drooping head"],
        "irregular_feather_appearance": ["ruffled feathers"],
    }
    result = run_module_semantic_mapping_pipeline(
        frames=["frame_a", "frame_b"],
        vision_client=FakeVisionClient(),
        raw_environment={
            "temperature_c": 31.5,
            "humidity_percent": 80,
            "ammonia_ppm": 5,
        },
        alias_map=alias_map,
        confidence_threshold=0.6,
    )

    assert result.visual_features == [
        VisualFeatureObservation("lowered_head_posture", 0.91),
        VisualFeatureObservation("irregular_feather_appearance", 0.72),
    ]
    assert result.environment_conditions == [
        "temperature_attention",
        "humidity_attention",
    ]
    assert result.unmapped_visuals == []
    assert result.manual_review_required is False
