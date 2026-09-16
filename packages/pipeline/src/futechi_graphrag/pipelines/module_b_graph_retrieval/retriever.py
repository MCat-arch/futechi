from collections.abc import Mapping
from typing import Any

from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)


def _as_list(params: Mapping[str, Any], key: str) -> list[str]:
    value = params.get(key, [])
    if not isinstance(value, list):
        raise TypeError(f"{key} must be a list")
    return value


def retrieve(
    params: Mapping[str, Any], disease_repository: DiseaseRepository
) -> GraphContext:
    """Retrieve graph candidates using already-built Modul B parameters."""
    return disease_repository.retrieve_context(
        visual_features=_as_list(params, "visual_features"),
        environment_conditions=_as_list(params, "environment_conditions"),
        excluded_disease_ids=_as_list(params, "excluded_disease_ids"),
    )
