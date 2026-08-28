from pathlib import Path
from typing import Any

import yaml

from futechi_graphrag.domain.value_objects.graph_context import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)


def is_context_empty(context: list[GraphContext] | None) -> bool:
    """Return whether retrieval produced no disease candidates."""
    return not context


def retry_with_fuzzy_expansion(
    params: dict[str, list[str]],
    disease_repository: DiseaseRepository,
    synonym_path: Path | None = None,
) -> list[GraphContext]:
    """Retry once with known synonyms added to the visual feature parameters."""
    path = synonym_path or (
        Path(__file__).parents[1]
        / "knowledge_graph"
        / "dictionaries"
        / "synonym_dictionary.yaml"
    )
    data: dict[str, list[str]] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    requested = list(params.get("visual_features", []))
    expanded: list[str] = []
    for canonical, synonyms in data.items():
        if canonical in requested or any(term in synonyms for term in requested):
            expanded.append(canonical)
    expanded = list(dict.fromkeys(expanded))
    retry_params = {
        "visual_features": expanded,
        "environment_conditions": list(params.get("environment_conditions", [])),
    }
    return disease_repository.retrieve_context(**retry_params)
