from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.llm.client import ImageInput, MultimodalLLMClient
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
    normalize_term,
)

from .canonical_mapper import map_to_canonical_terms
from .confidence_filter import filter_by_confidence
from .frame_aggregator import aggregate_candidates
from .mapping_validator import validate_mapping
from .mllm_extractor import DEFAULT_OBSERVATION_TARGETS, extract_frame_features
from .sensor_normalizer import normalize_environment
from .types import FrameExtractionResult, ModuleSemanticOutput


# ---------------------------------------------------------------------------
# Modul A: semantic mapping pipeline
# ---------------------------------------------------------------------------
#   1. ekstraksi fitur per frame dengan MLLM (kosakata tertutup dari ontologi)
#      -> extract_frame_features()          [node image_extraction]
#   2. canonical mapping per frame (nama canonical / sinonim)
#   3. agregasi multi-frame (majority) -- untuk fitur terpetakan & unmapped
#   4. filter confidence threshold
#   5. normalisasi sensor lingkungan (opsional)
#   6. validasi: tidak ada fitur / unmapped dominan -> manual review
#      -> map_extraction_result() langkah 2-6 [node semantic_mapping]
#
# Hasilnya `ModuleSemanticOutput` yang siap masuk Modul B. Tidak ada akses
# Neo4j di tahap ini.
# ---------------------------------------------------------------------------


def map_extraction_result(
    extraction: FrameExtractionResult,
    raw_environment: Mapping[str, float | None] | None = None,
    *,
    ontology_repository: OntologyRepository | None = None,
    observation_targets: Sequence[str] = DEFAULT_OBSERVATION_TARGETS,
    confidence_threshold: float = 0.6,
    min_frame_ratio: float = 0.5,
    unmapped_threshold_ratio: float = 0.5,
) -> ModuleSemanticOutput:
    """Langkah 2-6 Modul A: deterministik, tanpa panggilan model."""
    ontology = ontology_repository or OntologyRepository()
    vocabulary_names = [term.name for term in ontology.visual_feature_catalog(observation_targets)]
    alias_map = ontology.alias_map(vocabulary_names)

    mapped_raw, unmapped_raw = map_to_canonical_terms(extraction.candidates, alias_map)
    unmapped_raw = [replace(c, label=normalize_term(c.label)) for c in unmapped_raw]

    mapped = filter_by_confidence(
        aggregate_candidates(mapped_raw, extraction.frames_usable, min_frame_ratio),
        threshold=confidence_threshold,
    )
    unmapped = filter_by_confidence(
        aggregate_candidates(unmapped_raw, extraction.frames_usable, min_frame_ratio),
        threshold=confidence_threshold,
    )

    environment = raw_environment or {}
    env_conditions = normalize_environment(
        temperature_c=environment.get("temperature_c"),
        humidity_percent=environment.get("humidity_percent"),
        ammonia_ppm=environment.get("ammonia_ppm"),
    )

    manual_review_required, unmapped_ratio = validate_mapping(
        mapped_count=len(mapped),
        unmapped_count=len(unmapped),
        threshold_ratio=unmapped_threshold_ratio,
    )

    notes = list(extraction.notes)
    if extraction.frames_usable == 0:
        manual_review_required = True
        notes.append("Tidak ada frame yang dapat dinilai MLLM.")
    elif not mapped:
        notes.append("Tidak ada fitur canonical yang lolos agregasi dan filter confidence.")

    return ModuleSemanticOutput(
        visual_features=[VisualFeatureObservation(c.label, c.confidence) for c in mapped],
        environment_conditions=env_conditions,
        unmapped_visuals=[c.label for c in unmapped],
        unmapped_ratio=unmapped_ratio,
        manual_review_required=manual_review_required,
        frames_total=extraction.frames_total,
        frames_usable=extraction.frames_usable,
        notes=notes,
    )


def run_module_semantic_mapping_pipeline(
    frames: Sequence[ImageInput],
    mllm_client: MultimodalLLMClient,
    raw_environment: Mapping[str, float | None] | None = None,
    *,
    ontology_repository: OntologyRepository | None = None,
    capture_quality: str = "high",
    observation_targets: Sequence[str] = DEFAULT_OBSERVATION_TARGETS,
    confidence_threshold: float = 0.6,
    min_frame_ratio: float = 0.5,
    unmapped_threshold_ratio: float = 0.5,
) -> ModuleSemanticOutput:
    """Run the complete semantic mapping pipeline for Modul A (langkah 1-6)."""
    ontology = ontology_repository or OntologyRepository()
    extraction = extract_frame_features(
        frames,
        mllm_client,
        ontology.visual_feature_catalog(observation_targets),
        capture_quality,
    )
    return map_extraction_result(
        extraction,
        raw_environment,
        ontology_repository=ontology,
        observation_targets=observation_targets,
        confidence_threshold=confidence_threshold,
        min_frame_ratio=min_frame_ratio,
        unmapped_threshold_ratio=unmapped_threshold_ratio,
    )
