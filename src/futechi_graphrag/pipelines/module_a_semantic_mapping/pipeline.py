from __future__ import annotations

from .canonical_mapper import map_to_canonical_terms
from .confidence_filter import filter_by_confidence
from .frame_aggregator import aggregate_candidates
from .mapping_validator import validate_mapping
from .sensor_normalizer import normalize_environment
from .types import ModuleSemanticOutput
from .vlm_extractor import extract_raw_features


# ---------------------------------------------------------------------------
# Modul A: semantic mapping pipeline
# ---------------------------------------------------------------------------
# Pipeline ini menjalankan urutan berikut:
#   1. ekstraksi raw feature dari frame/VLM
#   2. agregasi multi-frame untuk mengurangi duplikasi
#   3. filter confidence threshold
#   4. mapping raw label ke istilah canonical ontology
#   5. normalisasi sensor/environment
#   6. validasi unmapped ratio
#
# Hasil akhirnya adalah `ModuleSemanticOutput`, yaitu payload yang siap masuk ke
# Modul B graph retrieval. Pada tahap ini kita TIDAK mengakses Neo4j sama sekali.
# ---------------------------------------------------------------------------


def run_module_semantic_mapping_pipeline(
    frames: list,
    vision_client: object,
    raw_environment: dict,
    alias_map: dict[str, list[str]],
    confidence_threshold: float = 0.6,
) -> ModuleSemanticOutput:
    """Run the complete semantic mapping pipeline for Modul A."""
    raw_candidates = extract_raw_features(frames, vision_client)
    aggregated = aggregate_candidates(raw_candidates)
    filtered = filter_by_confidence(aggregated, threshold=confidence_threshold)
    mapped_features, unmapped = map_to_canonical_terms(filtered, alias_map)

    env_conditions = normalize_environment(
        temperature_c=raw_environment.get("temperature_c"),
        humidity_percent=raw_environment.get("humidity_percent"),
        ammonia_ppm=raw_environment.get("ammonia_ppm"),
    )

    manual_review_required, unmapped_ratio = validate_mapping(
        mapped_count=len(mapped_features),
        unmapped_count=len(unmapped),
    )

    return ModuleSemanticOutput(
        visual_features=mapped_features,
        environment_conditions=env_conditions,
        unmapped_visuals=unmapped,
        unmapped_ratio=unmapped_ratio,
        manual_review_required=manual_review_required,
        notes=["Module A completed successfully."],
    )
