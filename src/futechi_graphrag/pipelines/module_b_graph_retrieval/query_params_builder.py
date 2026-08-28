from collections.abc import Iterable

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)


def build_params(
    visual_features: Iterable[VisualFeatureObservation],
    environment_conditions: Iterable[str],
    ontology_repository: OntologyRepository | None = None,
    confidence_threshold: float = 0.6,
) -> dict[str, list[str]]:
    """Build validated Neo4j parameters from Modul A observations."""
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0.0 and 1.0")

    ontology = ontology_repository or OntologyRepository()
    selected_features = [
        observation.name
        for observation in visual_features
        if observation.confidence >= confidence_threshold
    ]
    invalid_features = [
        name for name in selected_features
        if not ontology.is_valid_visual_feature(name)
    ]
    conditions = list(dict.fromkeys(environment_conditions))
    invalid_conditions = [
        name for name in conditions
        if not ontology.is_valid_environment_condition(name)
    ]
    if invalid_features or invalid_conditions:
        raise ValueError(
            "Unknown ontology terms: "
            f"visual_features={invalid_features}, "
            f"environment_conditions={invalid_conditions}"
        )

    return {
        "visual_features": list(dict.fromkeys(selected_features)),
        "environment_conditions": conditions,
    }
