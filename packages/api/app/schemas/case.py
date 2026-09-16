"""
Pydantic schema: kontrak request/response API.

Dipisah dari ORM supaya kontrak API stabil meski struktur DB berubah, dan
supaya aturan TAMPIL bertahap (Tahap 1 vs Tahap 2 reveal) ditegakkan di
lapisan serialisasi -- mitigasi & referensi obat hanya ikut terserialisasi
setelah user mengonfirmasi "Sakit".
"""

from datetime import datetime

from futechi_graphrag.domain.value_objects.enums import (
    CageStatus,
    CaseStatus,
    ConfirmationType,
    DetectionSession,
    SeverityLevel,
)
from typing import Annotated, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

T = TypeVar("T")

# Kolom JSON di DB bernilai NULL selama pipeline belum menulis hasil. Untuk
# klien, list kosong jauh lebih mudah ditangani daripada null, jadi None
# dinormalkan menjadi [] saat serialisasi.
ListOrNone = Annotated[list[T], BeforeValidator(lambda v: [] if v is None else v)]


# --------------------------------------------------------------------------
# Ingestion dari edge (Phase 2 -> Phase 3)
# --------------------------------------------------------------------------
class FrameMeta(BaseModel):
    """Metadata satu crop dari frame selection di edge."""

    fcos_confidence: float | None = None
    blur_score: float | None = None
    bbox: dict | None = None
    bbox_complete: bool | None = None
    neighbor_present: bool = False


class RawEnvironment(BaseModel):
    temperature_c: float | None = None
    humidity_percent: float | None = None
    ammonia_ppm: float | None = None


class CaseIngestRequest(BaseModel):
    """
    Payload JSON dari edge (crop dikirim terpisah sebagai multipart file).
    `event_id` membuat pengiriman ulang saat koneksi putus tidak menghasilkan
    case ganda.
    """

    event_id: str
    cage_id: str
    blok_id: str | None = None
    device_id: str | None = None
    detection_session: DetectionSession | None = None
    detected_at: datetime | None = None
    track_id: str | None = None
    mean_sick_confidence: float | None = None
    capture_quality: str = "high"
    raw_environment: RawEnvironment | None = None
    frames_meta: list[FrameMeta] = Field(default_factory=list)


class CaseIngestResponse(BaseModel):
    """
    `outcome` menjelaskan keputusan intake, bukan sekadar "ok":
    new_case | merged | skipped_excluded | skipped_cooldown |
    skipped_resolved_today | escalated_priority_review | duplicate_event
    """

    outcome: str
    case_id: str | None = None
    task_id: str | None = None
    status: CaseStatus | None = None
    alert_count: int | None = None
    message: str | None = None


# --------------------------------------------------------------------------
# Output case
# --------------------------------------------------------------------------
class VisualFeatureOut(BaseModel):
    name: str
    confidence: float


class RelatedConditionOut(BaseModel):
    disease_name: str
    evidence: list[str] = Field(default_factory=list)
    differential_note: str | None = None


class InspectionActionOut(BaseModel):
    name: str
    instruction: str


class MitigationActionOut(BaseModel):
    name: str
    instruction: str
    priority: str | None = None


class MedicalReferenceOut(BaseModel):
    for_condition: str
    treatment_name: str
    dosage: str
    withdrawal_period: str
    disclaimer: str


class FrameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    image_path: str
    order_index: int
    fcos_confidence: float | None
    blur_score: float | None
    neighbor_present: bool


class CaseSummaryOut(BaseModel):
    """Baris daftar alert."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    cage_id: str
    blok_id: str | None
    status: CaseStatus
    severity_level: SeverityLevel | None
    alert_count: int
    requires_manual_review: bool
    notifiable_notice: str | None
    created_at: datetime
    last_detected_at: datetime


class CaseDetailOut(CaseSummaryOut):
    """
    Detail satu case.

    Tahap 1 (PENDING_CONFIRMATION): related_conditions + recommended_checks.
    Tahap 2 (setelah "Sakit"): recommended_mitigations + medical_references
    terisi, di-scope HANYA ke penyakit yang dikonfirmasi.
    """

    capture_quality: str
    visual_features: ListOrNone[VisualFeatureOut] = Field(default_factory=list)
    environment_conditions: ListOrNone[str] = Field(default_factory=list)
    unmapped_visuals: ListOrNone[str] = Field(default_factory=list)
    raw_environment: dict | None = None

    related_conditions: ListOrNone[RelatedConditionOut] = Field(default_factory=list)
    recommended_checks: ListOrNone[InspectionActionOut] = Field(default_factory=list)
    severity_detail: dict | None = None
    overall_uncertainty: str | None = None

    recommended_mitigations: ListOrNone[MitigationActionOut] = Field(default_factory=list)
    medical_references: ListOrNone[MedicalReferenceOut] = Field(default_factory=list)

    confirmed_condition: str | None = None
    confirmed_by: str | None = None
    resolved_at: datetime | None = None

    pipeline_status: str | None = None
    pipeline_notes: ListOrNone[str] = Field(default_factory=list)
    error: str | None = None
    frames: ListOrNone[FrameOut] = Field(default_factory=list)


# --------------------------------------------------------------------------
# Konfirmasi user & siklus hidup cage
# --------------------------------------------------------------------------
class CaseConfirmRequest(BaseModel):
    """
    Tiga tombol di aplikasi. Untuk "sakit", `confirmed_condition` WAJIB diisi
    dengan salah satu nama dari related_conditions -- itu yang menentukan
    mitigasi & referensi obat mana yang dibuka.
    """

    confirmation: ConfirmationType
    confirmed_by: str
    confirmed_condition: str | None = None


class CageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    cage_id: str
    blok_id: str | None
    status: CageStatus
    cooldown_reason: str | None
    cooldown_cycles_remaining: int
    anomaly_count_during_cooldown: int
    active_case_id: str | None
    updated_at: datetime


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    asked_by: str | None = None


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    case_id: str
    reply: ChatMessageOut
    # Kandidat yang dipakai sebagai dasar jawaban giliran ini (audit grounding).
    graph_scope: ListOrNone[str] = Field(default_factory=list)
