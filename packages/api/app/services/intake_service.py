"""
Intake event dari edge (alur_sistem_terpadu.md Phase 3.2).

Keputusan intake dilakukan di SERVER (opsi K5-A): edge selalu mengirim event
terkonfirmasi, server yang memutuskan skip / gabung / buat case baru. Dengan
begitu anomali saat cooldown tetap tercatat dan safety-net bisa dihitung.

    event_id sudah pernah masuk        -> duplicate_event (idempoten)
    cage EXCLUDED_SICK                 -> skipped_excluded (dicatat saja)
    cage COOLDOWN                      -> skipped_cooldown, hitung anomali
        anomali ke-N (default 3)       -> escalated_priority_review (buat case)
    ada case belum dikonfirmasi        -> merged (alert_count++)
    case sudah resolved hari ini       -> skipped_resolved_today (Asumsi A2)
    selain itu                         -> new_case
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from futechi_graphrag.domain.policies.safety_net_policy import should_force_escalate
from futechi_graphrag.domain.value_objects.enums import CageStatus
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.case import Case
from app.services import case_service

settings = get_settings()


@dataclass
class IntakeDecision:
    outcome: str
    case: Case | None = None
    message: str | None = None

    @property
    def should_run_pipeline(self) -> bool:
        return self.outcome in {"new_case", "merged", "escalated_priority_review"}


def _released_after_resolution(cage, case) -> bool:
    """True bila cage dibebaskan manual SETELAH case terakhir dikonfirmasi."""
    if cage.status is not CageStatus.ELIGIBLE:
        return False
    if cage.updated_at is None or case.resolved_at is None:
        return False
    return cage.updated_at > case.resolved_at


async def decide_intake(
    db: AsyncSession,
    *,
    event_id: str,
    cage_id: str,
    blok_id: str | None,
    device_id: str | None,
    detection_session: Any | None,
    detected_at: datetime | None,
    capture_quality: str,
    mean_sick_confidence: float | None,
    raw_environment: dict | None,
) -> IntakeDecision:
    now = detected_at or datetime.now(timezone.utc)

    existing_event = await case_service.find_event(db, event_id)
    if existing_event is not None:
        return IntakeDecision(
            outcome="duplicate_event",
            message="event_id sudah pernah diproses; pengiriman ulang diabaikan.",
        )

    cage = await case_service.get_or_create_cage(db, cage_id, blok_id)

    async def _log(outcome: str, case: Case | None) -> None:
        await case_service.log_event(
            db,
            event_id=event_id,
            cage_id=cage_id,
            blok_id=blok_id,
            device_id=device_id,
            detection_session=detection_session,
            detected_at=now,
            outcome=outcome,
            case_id=case.id if case else None,
            mean_sick_confidence=mean_sick_confidence,
            capture_quality=capture_quality,
            raw_environment=raw_environment,
        )

    # 1. cage sedang ditangani -> jangan alert lagi untuk penyakit yang sama
    if cage.status is CageStatus.EXCLUDED_SICK:
        await _log("skipped_excluded", None)
        return IntakeDecision(
            outcome="skipped_excluded",
            message="Cage sedang dalam masa treatment (CONFIRMED_SICK).",
        )

    # 2. cooldown: dicatat di background; anomali berulang memicu eskalasi paksa
    if cage.status is CageStatus.COOLDOWN:
        cage.anomaly_count_during_cooldown += 1
        if should_force_escalate(
            cage.anomaly_count_during_cooldown, settings.safety_net_anomaly_count
        ):
            case = await case_service.create_case(
                db,
                cage=cage,
                device_id=device_id,
                detection_session=detection_session,
                capture_quality=capture_quality,
                raw_environment=raw_environment,
                detected_at=now,
            )
            cage.anomaly_count_during_cooldown = 0
            await _log("escalated_priority_review", case)
            return IntakeDecision(
                outcome="escalated_priority_review",
                case=case,
                message=(
                    f"Anomali berulang ke-{settings.safety_net_anomaly_count} selama cooldown: "
                    "dieskalasi ke petugas meski cage masih cooldown."
                ),
            )
        await _log("skipped_cooldown", None)
        return IntakeDecision(
            outcome="skipped_cooldown",
            message=(
                f"Cage masih cooldown ({cage.cooldown_cycles_remaining} siklus tersisa). "
                f"Anomali dicatat ({cage.anomaly_count_during_cooldown})."
            ),
        )

    # 3. masih ada case terbuka -> gabungkan evidence
    open_case = await case_service.get_open_case_for_cage(db, cage_id)
    if open_case is not None:
        case = await case_service.merge_detection(
            db,
            case=open_case,
            detection_session=detection_session,
            capture_quality=capture_quality,
            raw_environment=raw_environment,
            detected_at=now,
        )
        await _log("merged", case)
        return IntakeDecision(
            outcome="merged",
            case=case,
            message="Evidence digabung ke case yang belum dikonfirmasi.",
        )

    # 4. sudah dikonfirmasi hari ini -> sesi berikutnya di-skip (Asumsi A2),
    #    KECUALI petugas sudah menekan "Tandai Sembuh"/"Reset Monitoring"
    #    setelah case itu selesai -- tindakan manual berarti minta cage
    #    dipantau lagi, jadi tidak boleh diblokir aturan harian.
    resolved_today = await case_service.get_case_resolved_today(db, cage_id, now)
    if resolved_today is not None and not _released_after_resolution(cage, resolved_today):
        await _log("skipped_resolved_today", resolved_today)
        return IntakeDecision(
            outcome="skipped_resolved_today",
            case=resolved_today,
            message="Case untuk cage ini sudah dikonfirmasi hari ini.",
        )

    # 5. case baru
    case = await case_service.create_case(
        db,
        cage=cage,
        device_id=device_id,
        detection_session=detection_session,
        capture_quality=capture_quality,
        raw_environment=raw_environment,
        detected_at=now,
    )
    await _log("new_case", case)
    return IntakeDecision(outcome="new_case", case=case)
