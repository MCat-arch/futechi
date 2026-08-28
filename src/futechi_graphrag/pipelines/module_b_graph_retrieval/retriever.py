from collections.abc import Mapping
from typing import Any

from futechi_graphrag.domain.value_objects.graph_context import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)


def retrieve(
    params: Mapping[str, Any], disease_repository: DiseaseRepository
) -> list[GraphContext]:
    """Retrieve graph candidates using already-built Modul B parameters."""
    visual_features = params.get("visual_features", [])
    environment_conditions = params.get("environment_conditions", [])
    if not isinstance(visual_features, list) or not isinstance(
        environment_conditions, list
    ):
        raise TypeError("visual_features and environment_conditions must be lists")
    return disease_repository.retrieve_context(
        visual_features=visual_features,
        environment_conditions=environment_conditions,
    )
