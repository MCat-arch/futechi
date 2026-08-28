"""
Case: entitas inti yang merepresentasikan satu episode deteksi anomali
pada satu ekor ayam (per cage_id) sampai selesai dikonfirmasi user.

PENTING: entity ini SENGAJA tidak tahu apa-apa soal Neo4j, HTTP, database,
atau LangGraph -- murni model data + method yang mengubah state dirinya
sendiri. Semua method di sini adalah pure mutation (tidak ada I/O),
sehingga bisa diuji tanpa menyalakan service eksternal apa pun.

Urutan tampil informasi (PENTING, ini alasan ada 2 tahap attach/resolve):
1. Begitu case dibuat & reasoning selesai (status -> PENDING_CONFIRMATION):
   yang ditampilkan ke user HANYA related_conditions + recommended_checks
   (InspectionAction). Tujuannya membantu user MELAKUKAN pemeriksaan
   sebelum memutuskan tombol konfirmasi mana yang ditekan.
2. Begitu user menekan tombol "Sakit" dengan memilih salah satu penyakit:
   recommended_mitigations (MitigationAction) + medical_references
   (MedicalReference) BARU muncul, di-scope HANYA ke penyakit yang
   dikonfirmasi tsb -- bukan gabungan semua kandidat. Data untuk semua
   kandidat penyakit tetap disimpan di `_disease_actions` sejak awal
   (aksesnya tetap terbuka secara prinsip, sesuai keputusan desain),
   tapi baru "dibuka" ke field yang ditampilkan setelah ada kepastian
   penyakit mana yang relevan -- supaya user tidak dibanjiri rekomendasi
   obat untuk penyakit yang belum tentu benar.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from futechi_graphrag.domain.exceptions import CaseAlreadyResolvedError
from futechi_graphrag.domain.value_objects.enums import (CaseStatus, ConfirmationType, DetectionSession)
from futechi_graphrag.domain.value_objects.observation import (
    DiseaseActionBundle,
    EnvironmentSnapshot,
    InspectionAction,
    MedicalReference,
    MitigationAction,
    RelatedCondition,
    VisualFeatureObservation,
)
from futechi_graphrag.domain.value_objects.severity import SeverityResult

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
    cage_id: str
    status: CaseStatus
    alert_count: int
    detection_sessions: list[DetectionSession]
    visual_features: list[VisualFeatureObservation]
    environment_snapshot: EnvironmentSnapshot
    created_at: datetime
    last_detected_at: datetime

    # Tahap 1 : ditampilkan prediksi dan inspection action ke user dengan status PENDING_CONFIRMATION
    related_conditions: list[RelatedCondition] = field(default_factory=list)
    recomended_checks: list[InspectionAction] = field(default_factory=list)

    # Tahap 2 : ditampilkan mitigation action dan medical reference ke user setelah user konfirmasi penyakit
    recommended_mitigations: list[MitigationAction] = field(default_factory=list)
    medical_references: list[MedicalReference] = field(default_factory=list)

    # -- Data internal, TIDAK ditampilkan langsung ke user --
    # Berisi mitigasi + referensi medis untuk SEMUA kandidat penyakit,
    # dikelompokkan per nama penyakit. "Dibuka" sebagian ke
    # recommended_mitigations/medical_references saat resolve(SICK, ...)
    # sesuai penyakit yang dikonfirmasi.
    _disease_actions: dict[str, DiseaseActionBundle] = field(default_factory=dict)
    severity: SeverityResult | None = None
    resolved_at: datetime | None = None
    confirmed_by: str | None = None

    #FACTORY
    @classmethod
    def create_new(
        cls, 
        case_id: str,
        blok_id: str,
        cage_id: str,
        session: DetectionSession,
        visual_features: list[VisualFeatureObservation],
        environment_snapshot: EnvironmentSnapshot,
        now: datetime,
    ) -> "Case":
        """Buat Case baru dari deteksi pertama (bukan hasil merge)."""
        return cls(
            case_id=case_id,
            blok_id=blok_id,
            cage_id=cage_id,
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

    def known_candidate_diseases(self) -> tuple[str, ...]:
        """Kembalikan tuple nama penyakit yang sudah diketahui (dari hasil
        reasoning) untuk case ini. Bisa kosong jika reasoning belum
        selesai atau tidak menemukan kandidat penyakit sama sekali.
        """
        return tuple(rc.disease_name for rc in self.related_conditions)

    # MUTATION METHODS
    
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
        recommended_checks: list[InspectionAction],
        disease_actions: dict[str, DiseaseActionBundle],
        severity: SeverityResult | None,
    ) -> None:
        """
        Lampirkan hasil Modul C (LLM constrained reasoning) ke case ini,
        lalu ubah status menjadi PENDING_CONFIRMATION.

        Args:
            related_conditions: daftar kandidat penyakit + evidence +
                catatan diferensial -- LANGSUNG ditampilkan ke user.
            recommended_checks: tindakan pemeriksaan manual (InspectionAction)
                -- LANGSUNG ditampilkan ke user, membantu proses konfirmasi.
            disease_actions: mitigasi + referensi medis PER penyakit kandidat,
                key = nama penyakit. DISIMPAN dulu (belum ditampilkan) --
                baru dibuka sebagian lewat resolve() saat user konfirmasi
                "Sakit" dengan memilih salah satu penyakit ini.
            severity: hasil perhitungan severity dinamis (boleh None jika
                belum bisa dihitung, mis. onset_stage tidak diketahui).
        """
        self.related_conditions = related_conditions
        self.recommended_checks = recommended_checks
        self._disease_actions = disease_actions
        self.severity = severity
        self.status = CaseStatus.PENDING_CONFIRMATION

    def mark_insufficient_data(self) -> None:
        """
        Dipanggil saat Modul B tidak menemukan graph_context sama sekali
        (boundary check kosong) -- tetap PENDING_CONFIRMATION karena case
        tetap perlu direview manual oleh user, hanya saja tanpa
        related_conditions/recommended_checks dari graph.
        """
        self.related_conditions = []
        self.recommended_checks = []
        self._disease_actions = {}
        self.status = CaseStatus.PENDING_CONFIRMATION

    def resolve(
        self, confirmation_type: ConfirmationType, 
        confirmed_by: str, 
        now: datetime,
        confirmed_condition: str |None = None
    ) -> None:
        """
        Terapkan hasil konfirmasi user (tombol Sakit/Tidak Sakit/Sehat)
        ke case ini.

        Untuk ConfirmationType.SICK, `confirmed_condition` WAJIB diisi
        dengan salah satu nama penyakit dari `related_conditions` --
        begitu diterima, mitigasi & referensi medis untuk penyakit
        tersebut "dibuka" dari `_disease_actions` ke
        `recommended_mitigations`/`medical_references` (yang sebelumnya
        kosong sejak case dibuat).

        Jika confirmed_condition tidak ditemukan di `_disease_actions`
        (mis. user memilih nama penyakit di luar kandidat yang diketahui
        graph), recommended_mitigations/medical_references tetap kosong
        -- ini kasus tepi yang sebaiknya ditangani di use case layer
        dengan menampilkan pesan "belum ada data tindakan terverifikasi
        untuk kondisi ini, disarankan konsultasi manual".
        """
        if confirmation_type == ConfirmationType.SICK and not confirmed_condition:
            raise ValueError(
                "confirmed_condition wajib diisi ketika ConfirmationType.SICK"
            )

        status_by_confirmation = {
            ConfirmationType.SICK: CaseStatus.CONFIRMED_SICK,
            ConfirmationType.NOT_SICK: CaseStatus.CONFIRMED_NOT_SICK,
            ConfirmationType.HEALTHY: CaseStatus.CONFIRMED_HEALTHY,
        }
        self.status = status_by_confirmation[confirmation_type]
        self.confirmed_by = confirmed_by
        self.resolved_at = now

        if confirmation_type == ConfirmationType.SICK:
            bundle = self._disease_actions.get(confirmed_condition)
            if bundle is not None:
                self.recommended_mitigations = list(bundle.mitigations)
                self.medical_references = list(bundle.medical_references)
            else:
                self.recommended_mitigations = []
                self.medical_references = []

    def escalate_unconfirmed(self) -> None:
        """
        Dipanggil oleh TTL job harian jika case tidak dikonfirmasi sampai
        batas waktu. Tidak berefek apa pun jika case bukan sedang
        PENDING_CONFIRMATION (mis. sudah resolved lebih dulu).
        """
        if self.status != CaseStatus.PENDING_CONFIRMATION:
            return
        self.status = CaseStatus.UNCONFIRMED_ESCALATED