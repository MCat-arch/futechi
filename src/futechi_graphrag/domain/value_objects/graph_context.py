from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphContext:
    """Normalized disease context returned by the graph retrieval query."""

    disease_id: str
    disease_name: str
    disease_desc: str
    base_severity: str
    notifiable: bool
    matched_visual_features: tuple[dict[str, Any], ...]
    related_symptoms: tuple[dict[str, Any], ...]
    matched_environment: tuple[dict[str, Any], ...]
    inspection_actions: tuple[dict[str, Any], ...]
    mitigation_actions: tuple[dict[str, Any], ...]
    medical_treatments: tuple[dict[str, Any], ...]
