"""
ORM model database API.

Enum status SENGAJA di-import dari domain package (bukan didefinisikan ulang),
supaya nilai di database selalu sama dengan state machine di
`futechi_graphrag.domain`. Menyalin enum ke sini pernah membuat backend lama
memakai siklus hidup yang berbeda dari desain.

Relasi:
  Cage (1) --< (N) Case          : satu kandang punya banyak case sepanjang waktu
  Case (1) --< (N) Frame         : crop hasil frame selection di edge
  Case (1) --< (N) ChatMessage   : riwayat chat (sumber kebenaran, bukan checkpointer)
"""

import uuid
from datetime import datetime, timezone

from futechi_graphrag.domain.value_objects.enums import (
    CageStatus,
    CaseStatus,
    CooldownReason,
    DetectionSession,
    SeverityLevel,
)
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _enum(enum_type):
    """Simpan NILAI enum ("confirmed_sick"), bukan nama ("CONFIRMED_SICK")."""
    return Enum(enum_type, values_callable=lambda e: [item.value for item in e])


class Cage(Base):
    """
    Status monitoring satu kandang (1 cage = 1 ekor, sesuai keputusan desain).
    Menentukan apakah anomali baru boleh memunculkan alert (exclusion/cooldown).
    """

    __tablename__ = "cages"

    cage_id: Mapped[str] = mapped_column(String, primary_key=True)
    blok_id: Mapped[str | None] = mapped_column(String, index=True)

    status: Mapped[CageStatus] = mapped_column(
        _enum(CageStatus), default=CageStatus.ELIGIBLE, index=True
    )
    cooldown_reason: Mapped[CooldownReason | None] = mapped_column(_enum(CooldownReason))
    cooldown_cycles_remaining: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_count_during_cooldown: Mapped[int] = mapped_column(Integer, default=0)
    active_case_id: Mapped[str | None] = mapped_column(String, index=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    cases: Mapped[list["Case"]] = relationship(back_populates="cage")


class Case(Base):
    """Satu episode deteksi anomali sampai dikonfirmasi user."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)

    cage_id: Mapped[str] = mapped_column(ForeignKey("cages.cage_id"), index=True)
    blok_id: Mapped[str | None] = mapped_column(String, index=True)
    device_id: Mapped[str | None] = mapped_column(String, index=True)

    status: Mapped[CaseStatus] = mapped_column(
        _enum(CaseStatus), default=CaseStatus.DETECTED, index=True
    )
    alert_count: Mapped[int] = mapped_column(Integer, default=1)
    detection_sessions: Mapped[list | None] = mapped_column(JSON)
    capture_quality: Mapped[str] = mapped_column(String, default="high")
    requires_manual_review: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- hasil Modul A ---
    visual_features: Mapped[list | None] = mapped_column(JSON)  # [{name, confidence}]
    environment_conditions: Mapped[list | None] = mapped_column(JSON)
    unmapped_visuals: Mapped[list | None] = mapped_column(JSON)
    raw_environment: Mapped[dict | None] = mapped_column(JSON)

    # --- hasil Modul C (Tahap 1 reveal: langsung tampil) ---
    related_conditions: Mapped[list | None] = mapped_column(JSON)
    recommended_checks: Mapped[list | None] = mapped_column(JSON)
    severity_level: Mapped[SeverityLevel | None] = mapped_column(_enum(SeverityLevel))
    severity_detail: Mapped[dict | None] = mapped_column(JSON)
    overall_uncertainty: Mapped[str | None] = mapped_column(Text)
    notifiable_notice: Mapped[str | None] = mapped_column(Text)

    # --- Tahap 2 reveal: disimpan sejak awal, BARU ditampilkan setelah "Sakit" ---
    disease_actions: Mapped[dict | None] = mapped_column(JSON)
    recommended_mitigations: Mapped[list | None] = mapped_column(JSON)
    medical_references: Mapped[list | None] = mapped_column(JSON)

    # --- konfirmasi user ---
    confirmed_condition: Mapped[str | None] = mapped_column(String)
    confirmed_by: Mapped[str | None] = mapped_column(String)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    task_id: Mapped[str | None] = mapped_column(String, index=True)
    pipeline_status: Mapped[str | None] = mapped_column(String)  # status graph
    pipeline_notes: Mapped[list | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    cage: Mapped["Cage"] = relationship(back_populates="cases")
    frames: Mapped[list["Frame"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class Frame(Base):
    """Satu crop hasil frame selection di edge (Phase 2)."""

    __tablename__ = "frames"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)

    event_id: Mapped[str | None] = mapped_column(String, index=True)
    image_path: Mapped[str] = mapped_column(String)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    fcos_confidence: Mapped[float | None] = mapped_column(Float)
    blur_score: Mapped[float | None] = mapped_column(Float)  # varians Laplacian
    bbox: Mapped[dict | None] = mapped_column(JSON)
    bbox_complete: Mapped[bool | None] = mapped_column(Boolean)
    neighbor_present: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    case: Mapped["Case"] = relationship(back_populates="frames")


class ChatMessage(Base):
    """
    Riwayat chat per case. INI sumber kebenaran percakapan (bukan checkpointer
    LangGraph): tiap giliran, pesan dibaca dari sini lalu dikirim ke chat graph.
    """

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)

    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    # Cakupan kandidat saat jawaban dibuat -- untuk audit jawaban LLM.
    graph_scope: Mapped[list | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    case: Mapped["Case"] = relationship(back_populates="chat_messages")


class DetectionEvent(Base):
    """
    Log semua event dari edge, termasuk yang TIDAK menjadi case (cage sedang
    di-exclude atau cooldown). Dipakai safety-net (>=3 anomali saat cooldown)
    dan audit.
    """

    __tablename__ = "detection_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    event_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    cage_id: Mapped[str] = mapped_column(String, index=True)
    blok_id: Mapped[str | None] = mapped_column(String)
    device_id: Mapped[str | None] = mapped_column(String)
    detection_session: Mapped[DetectionSession | None] = mapped_column(
        _enum(DetectionSession)
    )
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    outcome: Mapped[str] = mapped_column(String, index=True)
    # "new_case" | "merged" | "skipped_excluded" | "skipped_cooldown"
    # | "skipped_resolved_today" | "escalated_priority_review"
    case_id: Mapped[str | None] = mapped_column(String, index=True)

    mean_sick_confidence: Mapped[float | None] = mapped_column(Float)
    capture_quality: Mapped[str | None] = mapped_column(String)
    raw_environment: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
