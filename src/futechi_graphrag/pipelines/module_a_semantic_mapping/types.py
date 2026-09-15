from dataclasses import dataclass, field

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation


# ---------------------------------------------------------------------------
# Modul A contract
# ---------------------------------------------------------------------------
# `RawVisualCandidate`         : satu label per frame dari MLLM (belum tentu canonical).
# `AggregatedVisualCandidate`  : label setelah digabung lintas frame (majority).
# `FrameExtractionResult`      : hasil ekstraksi seluruh frame untuk satu case.
# `ModuleSemanticOutput`       : kontrak final Modul A yang masuk ke Modul B.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RawVisualCandidate:
    """Satu label dari satu frame, sebelum/ sesudah canonical mapping."""

    label: str
    confidence: float
    source_frame: str | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class AggregatedVisualCandidate:
    """Label hasil agregasi lintas frame."""

    label: str
    confidence: float  # rata-rata confidence pada frame tempat label muncul
    frame_support: int  # jumlah frame tempat label muncul
    frames_usable: int


@dataclass(frozen=True)
class FrameExtractionResult:
    candidates: list[RawVisualCandidate]
    frames_total: int
    frames_usable: int
    notes: list[str] = field(default_factory=list)


@dataclass
class ModuleSemanticOutput:
    """Final output contract for Modul A before graph retrieval."""

    visual_features: list[VisualFeatureObservation]
    environment_conditions: list[str]
    # Label mentah (sudah dinormalisasi) yang lolos agregasi tapi tidak
    # terpetakan -- dipakai retry Modul B.
    unmapped_visuals: list[str] = field(default_factory=list)
    unmapped_ratio: float = 0.0
    manual_review_required: bool = False
    frames_total: int = 0
    frames_usable: int = 0
    notes: list[str] = field(default_factory=list)
