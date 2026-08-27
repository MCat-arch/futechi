"""
Case: entitas inti yang merepresentasikan satu episode deteksi anomali
pada satu ekor ayam (per blok_id) sampai selesai dikonfirmasi user.

PENTING: entity ini SENGAJA tidak tahu apa-apa soal Neo4j, HTTP, database,
atau LangGraph -- murni model data + method yang mengubah state dirinya
sendiri. Semua method di sini adalah pure mutation (tidak ada I/O),
sehingga bisa diuji tanpa menyalakan service eksternal apa pun.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime

from futechi_graphrag.domain.exceptions import CaseAlreadyResolvedError
from futechi_graphrag.domain.value_objects.enums import (CaseStatus, ConfirmationType, DetectionSession)
from futechi_graphrag.domain.value_objects.observations import (
    EnvironmentSnapshot,
    MedicalReference,
    RelatedCondition,
    VisualFeatureObservation,
)
from poultry_graphrag.domain.value_objects.severity import SeverityResult

# Status yang dianggap "sudah selesai" -- case dengan status ini tidak boleh
# diproses ulang lagi di hari yang sama (lihat merge_new_detection).
RESOLVED_STATUSES = frozenset(
    {
        CaseStatus.CONFIRMED_SICK,
        CaseStatus.CONFIRMED_NOT_SICK,
        CaseStatus.CONFIRMED_HEALTHY,
    }
)

@dataclass
class Case:
    case_id: str
    blok_id: str
    status: CaseStatus
    alert_count: int
    detection_sessions: list[DetectionSession]
    visual_features: list[VisualFeatureObservation]
    environment_snapshot: EnvironmentSnapshot
    created_at: datetime
    last_detected_at: datetime

    related_conditions: list[RelatedCondition] = field(default_factory=list)
    medical_references: list[MedicalReference] = field(default_factory=list)
    severity: SeverityResult | None = None
    resolved_at: datetime | None = None
    confirmed_by: str | None = None

    #FACTORY
    @classmethod
    def create_new(
        cls, 
        case_id: str,
        blok_id: str,
        session: DetectionSession,
        visual_features: list[VisualFeatureObservation],
        environment_snapshot: EnvironmentSnapshot,
        now: datetime,
    ) -> "Case":
        """Buat Case baru dari deteksi pertama (bukan hasil merge)."""
        return cls(
            case_id=case_id,
            blok_id=blok_id,
            status=CaseStatus.DETECTED,
            alert_count=1,
            detection_sessions=[session],
            visual_features=list(visual_features),
            environment_snapshot=environment_snapshot,
            created_at=now,
            last_detected_at=now,
        )

    #QUERY METHODS
    def is_resolved(self) -> bool:
        return self.status in RESOLVED_STATUSES

    def is_same_day(self, other_time: datetime) -> bool:
        return self.last_detected_at.date() == other_time.date()

    def is_ttl_expired(self, ttl_hours: int, now: datetime) -> bool:
        """
        True hanya jika case masih PENDING_CONFIRMATION dan sudah melewati
        batas waktu. Case yang sudah resolved/escalated tidak dianggap
        "expired" lagi (sudah ditangani lewat jalur lain).
        """
        if self.status != CaseStatus.PENDING_CONFIRMATION:
            return False
        deadline = self.created_at + timedelta(hours=ttl_hours)
        return now >= deadline


    # MUTATION METHODS
    ####NEED CPNFIRMATION DAN TINJAUAN

    ###

    ### INI WOY
    ### BACAAA

    ### TODO: baca pada bagian fungsi attach_reasoning_result disitu hanya include medical nya, bukan nya include juga InspectionAction dan MitigationAction di AWAL
    ### TODO: TINJAU INI BESOK
    
    def merge_new_detection(
        self,
        session: DetectionSession,
        visual_features: list[VisualFeatureObservation],
        environment_snapshot: EnvironmentSnapshot,
        now: datetime,
    ) -> None:
        """
        Gabungkan evidence dari deteksi baru (mis. sesi ke-2 di hari yang
        sama, sebelum user sempat konfirmasi) ke case yang sudah ada --
        TIDAK membuat case baru. Menambah alert_count sesuai kesepakatan
        desain ("menambah alert sampai user konfirmasi").

        Guard: jika case sudah resolved DI HARI YANG SAMA, method ini
        menolak (raise). Idealnya use case layer sudah mencegah pemanggilan
        ini sejak awal (skip sesi ke-2 untuk cage yang sudah settled) --
        exception ini adalah lapisan pertahanan kedua.
        """
        if self.is_resolved() and self.is_same_day(now):
            raise CaseAlreadyResolvedError(self.case_id)

        self.alert_count += 1
        self.detection_sessions.append(session)

        existing_names = {f.name for f in self.visual_features}
        for feature in visual_features:
            if feature.name not in existing_names:
                self.visual_features.append(feature)
                existing_names.add(feature.name)

        self.environment_snapshot = environment_snapshot  # ambil snapshot terbaru
        self.last_detected_at = now

    def attach_reasoning_result(
        self,
        related_conditions: list[RelatedCondition],
        medical_references: list[MedicalReference],
        severity: SeverityResult | None,
    ) -> None:
        """
        Lampirkan hasil Modul C (LLM constrained reasoning) ke case ini,
        lalu ubah status menjadi PENDING_CONFIRMATION (siap ditampilkan
        ke user untuk dikonfirmasi).
        """
        self.related_conditions = related_conditions
        self.medical_references = medical_references
        self.severity = severity
        self.status = CaseStatus.PENDING_CONFIRMATION

    def mark_insufficient_data(self) -> None:
        """
        Dipanggil saat Modul B tidak menemukan graph_context sama sekali
        (boundary check kosong) -- tetap PENDING_CONFIRMATION karena case
        tetap perlu direview manual oleh user, hanya saja tanpa
        related_conditions/medical_references dari graph.
        """
        self.related_conditions = []
        self.medical_references = []
        self.status = CaseStatus.PENDING_CONFIRMATION

    def resolve(
        self, confirmation_type: ConfirmationType, confirmed_by: str, now: datetime
    ) -> None:
        """Terapkan hasil konfirmasi user (tombol Sakit/Tidak Sakit/Sehat) ke case ini."""
        status_by_confirmation = {
            ConfirmationType.SICK: CaseStatus.CONFIRMED_SICK,
            ConfirmationType.NOT_SICK: CaseStatus.CONFIRMED_NOT_SICK,
            ConfirmationType.HEALTHY: CaseStatus.CONFIRMED_HEALTHY,
        }
        self.status = status_by_confirmation[confirmation_type]
        self.confirmed_by = confirmed_by
        self.resolved_at = now

    def escalate_unconfirmed(self) -> None:
        """
        Dipanggil oleh TTL job harian jika case tidak dikonfirmasi sampai
        batas waktu. Tidak berefek apa pun jika case bukan sedang
        PENDING_CONFIRMATION (mis. sudah resolved lebih dulu).
        """
        if self.status != CaseStatus.PENDING_CONFIRMATION:
            return
        self.status = CaseStatus.UNCONFIRMED_ESCALATED