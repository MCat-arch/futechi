"""
Service layer Case: query, penyimpanan hasil pipeline, dan konfirmasi user.

Validasi perpindahan status memakai tabel transisi milik domain
(`VALID_TRANSITIONS`) supaya aturan siklus hidup hanya punya SATU sumber
kebenaran, tidak ditulis ulang di API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from futechi_graphrag.domain.value_objects.enums import (
    CageStatus,
    CaseStatus,
    ConfirmationType,
    CooldownReason,
)
from futechi_graphrag.domain.state_machine.case_state_machine import (
    VALID_TRANSITIONS,
    StateEventType,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.models.case import Cage, Case, ChatMessage, DetectionEvent, Frame
from app.services.mapping import pipeline_state_to_json

settings = get_settings()

OPEN_CASE_STATUSES = (CaseStatus.DETECTED, CaseStatus.PENDING_CONFIRMATION, CaseStatus.UNCONFIRMED_ESCALATED)
RESOLVED_CASE_STATUSES = (
    CaseStatus.CONFIRMED_SICK,
    CaseStatus.CONFIRMED_NOT_SICK,
    CaseStatus.CONFIRMED_HEALTHY,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Query
# --------------------------------------------------------------------------
async def get_case(db: AsyncSession, case_id: str) -> Case | None:
    stmt = (
        select(Case).where(Case.id == case_id).options(selectinload(Case.frames))
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_cases(
    db: AsyncSession,
    *,
    status: CaseStatus | None = None,
    cage_id: str | None = None,
    limit: int = 50,
) -> list[Case]:
    stmt = select(Case).order_by(Case.last_detected_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Case.status == status)
    if cage_id:
        stmt = stmt.where(Case.cage_id == cage_id)
    return list((await db.execute(stmt)).scalars().all())


async def get_open_case_for_cage(db: AsyncSession, cage_id: str) -> Case | None:
    """Case yang belum dikonfirmasi user (dasar penggabungan evidence)."""
    stmt = (
        select(Case)
        .where(Case.cage_id == cage_id, Case.status.in_(OPEN_CASE_STATUSES))
        .order_by(Case.last_detected_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_case_resolved_today(db: AsyncSession, cage_id: str, now: datetime) -> Case | None:
    """Asumsi A2: cage yang sudah settled hari ini tidak dideteksi ulang."""
    stmt = (
        select(Case)
        .where(Case.cage_id == cage_id, Case.status.in_(RESOLVED_CASE_STATUSES))
        .order_by(Case.resolved_at.desc())
        .limit(1)
    )
    case = (await db.execute(stmt)).scalar_one_or_none()
    if case and case.resolved_at and case.resolved_at.date() == now.date():
        return case
    return None


async def get_or_create_cage(db: AsyncSession, cage_id: str, blok_id: str | None) -> Cage:
    cage = await db.get(Cage, cage_id)
    if cage is None:
        cage = Cage(cage_id=cage_id, blok_id=blok_id, status=CageStatus.ELIGIBLE)
        db.add(cage)
        await db.flush()
    elif blok_id and cage.blok_id != blok_id:
        cage.blok_id = blok_id
    return cage


async def find_event(db: AsyncSession, event_id: str) -> DetectionEvent | None:
    stmt = select(DetectionEvent).where(DetectionEvent.event_id == event_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def log_event(
    db: AsyncSession,
    *,
    event_id: str,
    cage_id: str,
    blok_id: str | None,
    device_id: str | None,
    detection_session: Any | None,
    detected_at: datetime | None,
    outcome: str,
    case_id: str | None,
    mean_sick_confidence: float | None,
    capture_quality: str | None,
    raw_environment: dict | None,
) -> DetectionEvent:
    event = DetectionEvent(
        event_id=event_id,
        cage_id=cage_id,
        blok_id=blok_id,
        device_id=device_id,
        detection_session=detection_session,
        detected_at=detected_at,
        outcome=outcome,
        case_id=case_id,
        mean_sick_confidence=mean_sick_confidence,
        capture_quality=capture_quality,
        raw_environment=raw_environment,
    )
    db.add(event)
    return event


# --------------------------------------------------------------------------
# Mutasi
# --------------------------------------------------------------------------
async def create_case(
    db: AsyncSession,
    *,
    cage: Cage,
    device_id: str | None,
    detection_session: Any | None,
    capture_quality: str,
    raw_environment: dict | None,
    detected_at: datetime | None,
) -> Case:
    case = Case(
        cage_id=cage.cage_id,
        blok_id=cage.blok_id,
        device_id=device_id,
        status=CaseStatus.DETECTED,
        alert_count=1,
        detection_sessions=[detection_session.value] if detection_session else [],
        capture_quality=capture_quality,
        raw_environment=raw_environment,
        last_detected_at=detected_at or _now(),
    )
    db.add(case)
    await db.flush()
    cage.active_case_id = case.id
    return case


async def merge_detection(
    db: AsyncSession,
    *,
    case: Case,
    detection_session: Any | None,
    capture_quality: str,
    raw_environment: dict | None,
    detected_at: datetime | None,
) -> Case:
    """
    Asumsi A3: deteksi ulang sebelum dikonfirmasi menambah alert pada case yang
    SAMA, bukan membuat case baru.
    """
    case.alert_count += 1
    case.last_detected_at = detected_at or _now()
    case.capture_quality = capture_quality
    if raw_environment:
        case.raw_environment = raw_environment
    if detection_session:
        sessions = list(case.detection_sessions or [])
        sessions.append(detection_session.value)
        case.detection_sessions = sessions
    return case


async def add_frame(
    db: AsyncSession,
    *,
    case_id: str,
    event_id: str,
    image_path: str,
    order_index: int,
    meta: Any | None,
) -> Frame:
    frame = Frame(
        case_id=case_id,
        event_id=event_id,
        image_path=image_path,
        order_index=order_index,
        fcos_confidence=getattr(meta, "fcos_confidence", None),
        blur_score=getattr(meta, "blur_score", None),
        bbox=getattr(meta, "bbox", None),
        bbox_complete=getattr(meta, "bbox_complete", None),
        neighbor_present=getattr(meta, "neighbor_present", False),
    )
    db.add(frame)
    return frame


async def count_frames(db: AsyncSession, case_id: str) -> int:
    """
    Jumlah frame yang sudah tersimpan untuk case ini.

    Dipakai menentukan order_index frame berikutnya saat evidence digabung.
    SENGAJA query COUNT, bukan len(case.frames): relasi yang belum di-load
    akan memicu lazy load, dan lazy load di konteks async menyebabkan
    MissingGreenlet.
    """
    stmt = select(func.count()).select_from(Frame).where(Frame.case_id == case_id)
    return int((await db.execute(stmt)).scalar_one())


async def set_case_task(db: AsyncSession, case_id: str, task_id: str) -> None:
    case = await db.get(Case, case_id)
    if case:
        case.task_id = task_id


async def save_pipeline_result(db: AsyncSession, case_id: str, state: dict[str, Any]) -> Case | None:
    """
    Simpan hasil diagnostic_graph (dipanggil dari Celery worker).

    Status case SELALU menjadi PENDING_CONFIRMATION -- termasuk saat pipeline
    berakhir di fallback, karena case tetap perlu dilihat manusia. Yang
    membedakan hanya `requires_manual_review` dan isi related_conditions.
    """
    case = await db.get(Case, case_id)
    if case is None:
        return None

    payload = pipeline_state_to_json(state)
    for field, value in payload.items():
        setattr(case, field, value)

    case.status = CaseStatus.PENDING_CONFIRMATION
    case.error = state.get("error")
    return case


async def mark_case_failed(db: AsyncSession, case_id: str, error: str) -> None:
    case = await db.get(Case, case_id)
    if case:
        case.error = error
        case.pipeline_status = "failed"


async def confirm_case(
    db: AsyncSession,
    *,
    case: Case,
    confirmation: ConfirmationType,
    confirmed_by: str,
    confirmed_condition: str | None,
) -> Case:
    """
    Terapkan tombol konfirmasi ke case + cage.

    Untuk "sakit", mitigasi & referensi obat penyakit terkonfirmasi dibuka dari
    `disease_actions` (Tahap 2 reveal). Kalau penyakitnya tidak ada di kandidat
    graph, kedua field tetap kosong -- itu dilaporkan ke user sebagai
    "belum ada data tindakan terverifikasi", bukan dikarang.
    """
    if StateEventType.USER_CONFIRMED not in VALID_TRANSITIONS.get(case.status, frozenset()):
        raise ValueError(
            f"Case berstatus {case.status.value} tidak bisa dikonfirmasi lagi."
        )
    if confirmation is ConfirmationType.SICK and not confirmed_condition:
        raise ValueError("confirmed_condition wajib diisi untuk konfirmasi 'sakit'.")

    status_by_confirmation = {
        ConfirmationType.SICK: CaseStatus.CONFIRMED_SICK,
        ConfirmationType.NOT_SICK: CaseStatus.CONFIRMED_NOT_SICK,
        ConfirmationType.HEALTHY: CaseStatus.CONFIRMED_HEALTHY,
    }
    case.status = status_by_confirmation[confirmation]
    case.confirmed_by = confirmed_by
    case.confirmed_condition = confirmed_condition
    case.resolved_at = _now()

    if confirmation is ConfirmationType.SICK:
        bundle = (case.disease_actions or {}).get(confirmed_condition or "", {})
        case.recommended_mitigations = bundle.get("mitigations", [])
        case.medical_references = bundle.get("medical_references", [])

    cage = await get_or_create_cage(db, case.cage_id, case.blok_id)
    if confirmation is ConfirmationType.SICK:
        cage.status = CageStatus.EXCLUDED_SICK
        cage.cooldown_reason = None
        cage.cooldown_cycles_remaining = 0
        cage.anomaly_count_during_cooldown = 0
        cage.active_case_id = case.id
    else:
        cage.status = CageStatus.COOLDOWN
        cage.cooldown_reason = (
            CooldownReason.NOT_SICK
            if confirmation is ConfirmationType.NOT_SICK
            else CooldownReason.FALSE_ALARM
        )
        cage.cooldown_cycles_remaining = settings.cooldown_cycles
        cage.anomaly_count_during_cooldown = 0
        cage.active_case_id = None

    return case


async def release_cage(db: AsyncSession, cage_id: str) -> Cage | None:
    """Tombol "Tandai Sembuh" / "Reset Monitoring Cage" -- selalu manual."""
    cage = await db.get(Cage, cage_id)
    if cage is None:
        return None
    cage.status = CageStatus.ELIGIBLE
    cage.cooldown_reason = None
    cage.cooldown_cycles_remaining = 0
    cage.anomaly_count_during_cooldown = 0
    cage.active_case_id = None
    return cage


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
async def list_chat_messages(db: AsyncSession, case_id: str, limit: int = 50) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.case_id == case_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def add_chat_message(
    db: AsyncSession,
    *,
    case_id: str,
    role: str,
    content: str,
    graph_scope: list[str] | None = None,
) -> ChatMessage:
    message = ChatMessage(
        case_id=case_id, role=role, content=content, graph_scope=graph_scope
    )
    db.add(message)
    await db.flush()
    return message


async def recent_resolved_cases(
    db: AsyncSession, *, cage_id: str, exclude_case_id: str, limit: int, since: datetime
) -> list[Case]:
    stmt = (
        select(Case)
        .where(
            Case.cage_id == cage_id,
            Case.id != exclude_case_id,
            Case.status.in_(RESOLVED_CASE_STATUSES),
            Case.resolved_at.is_not(None),
            Case.resolved_at >= since,
        )
        .order_by(Case.resolved_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
