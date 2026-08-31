from dataclasses import dataclass, field

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation


# ---------------------------------------------------------------------------
# Modul A contract
# ---------------------------------------------------------------------------
# `RawVisualCandidate` adalah output mentah dari VLM sebelum proses mapping
# ke istilah canonical. Data ini masih kasar, belum memiliki semantik domain,
# dan belum tentu relevan untuk query Neo4j.
#
# `ModuleSemanticOutput` adalah kontrak final Modul A yang akan masuk ke Modul B
# untuk dibangun menjadi query param dan dieksekusi di graph retrieval.
# ---------------------------------------------------------------------------


@dataclass
class RawVisualCandidate:
    """Raw VLM output before semantic canonicalization."""

    label: str
    confidence: float
    source_frame: str | None = None


@dataclass
class ModuleSemanticOutput:
    """Final output contract for Modul A before graph retrieval."""

    visual_features: list[VisualFeatureObservation]
    environment_conditions: list[str]
    unmapped_visuals: list[str] = field(default_factory=list)
    unmapped_ratio: float = 0.0
    manual_review_required: bool = False
    notes: list[str] = field(default_factory=list)
