from pathlib import Path
from typing import Any

import yaml


class OntologyRepository:
    """Read and cache canonical terms used to validate retrieval parameters."""

    def __init__(self, canonical_terms_path: Path | None = None) -> None:
        path = canonical_terms_path or (
            Path(__file__).parents[3]
            / "pipelines"
            / "knowledge_graph"
            / "dictionaries"
            / "canonical_terms.yaml"
        )
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        self._visual_features = frozenset(data.get("visual_features", []))
        self._environment_conditions = frozenset(
            data.get("environment_conditions", [])
        )

    def is_valid_visual_feature(self, name: str) -> bool:
        """Return whether a visual feature is a canonical ontology term."""
        return name in self._visual_features

    def is_valid_environment_condition(self, name: str) -> bool:
        """Return whether an environment condition is canonical."""
        return name in self._environment_conditions
