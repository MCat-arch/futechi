"""
Route case: ingestion dari edge, daftar alert, detail, dan tombol konfirmasi.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from futechi_graphrag.domain.value_objects.enums import CaseStatus
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.schemas.case import (
    CaseConfirmRequest,
    CaseDetailOut,
    CaseIngestRequest,
    CaseIngestResponse,
    CaseSummaryOut,
)
from app.services import case_service, intake_service
from app.services.preprocessing import save_and_preprocess
from app.tasks.worker import process_case_task

router = APIRouter(prefix="/cases", tags=["cases"])
settings = get_settings()


@router.post("", response_model=CaseIngestResponse, status_code=202)
async def ingest_case(
    metadata: str = Form(..., description="JSON sesuai CaseIngestRequest"),
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Ingestion event dari edge (host Pi).

    Server yang memutuskan nasib event (buat case / gabung / skip), lalu
    memicu diagnostic_graph lewat Celery. Respons langsung, tidak menunggu
    pipeline selesai.
    """
    try:
        payload = CaseIngestRequest(**json.loads(metadata))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"metadata JSON tidak valid: {exc}") from exc

    if not images:
        raise HTTPException(400, "minimal satu gambar crop diperlukan")
    if len(images) > settings.max_frames_per_case:
        raise HTTPException(
            400, f"maksimal {settings.max_frames_per_case} frame per event"
        )

    raw_environment = (
        payload.raw_environment.model_dump() if payload.raw_environment else None
    )

    decision = await intake_service.decide_intake(
        db,
        event_id=payload.event_id,
        cage_id=payload.cage_id,
        blok_id=payload.blok_id,
        device_id=payload.device_id,
        detection_session=payload.detection_session,
        detected_at=payload.detected_at,
        capture_quality=payload.capture_quality,
        mean_sick_confidence=payload.mean_sick_confidence,
        raw_environment=raw_environment,
    )

    if not decision.should_run_pipeline or decision.case is None:
        return CaseIngestResponse(
            outcome=decision.outcome,
            case_id=decision.case.id if decision.case else None,
            status=decision.case.status if decision.case else None,
            message=decision.message,
        )

    case = decision.case
    image_paths: list[str] = []
    existing_frames = await case_service.count_frames(db, case.id)
    for index, upload in enumerate(images):
        raw = await upload.read()
        path = save_and_preprocess(raw, case.id, existing_frames + index)
        image_paths.append(path)
        meta = payload.frames_meta[index] if index < len(payload.frames_meta) else None
        await case_service.add_frame(
            db,
            case_id=case.id,
            event_id=payload.event_id,
            image_path=path,
            order_index=existing_frames + index,
            meta=meta,
        )

    task = process_case_task.delay(
        case.id,
        case.cage_id,
        case.blok_id,
        image_paths,
        payload.capture_quality,
        raw_environment,
        None,
    )
    await case_service.set_case_task(db, case.id, task.id)

    return CaseIngestResponse(
        outcome=decision.outcome,
        case_id=case.id,
        task_id=task.id,
        status=case.status,
        alert_count=case.alert_count,
        message=decision.message,
    )


@router.get("", response_model=list[CaseSummaryOut])
async def list_cases(
    status: CaseStatus | None = None,
    cage_id: str | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Daftar alert. Default: yang terbaru lebih dulu."""
    return await case_service.list_cases(db, status=status, cage_id=cage_id, limit=limit)


@router.get("/{case_id}", response_model=CaseDetailOut)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)):
    case = await case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(404, "case tidak ditemukan")
    return case


@router.post("/{case_id}/confirm", response_model=CaseDetailOut)
async def confirm_case(
    case_id: str,
    request: CaseConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Tombol [Sakit] / [Tidak Sakit] / [Sehat].

    Untuk "sakit", mitigasi & referensi obat penyakit yang dikonfirmasi baru
    dibuka di sini (Tahap 2 reveal), dan cage dikecualikan sampai petugas
    menekan "Tandai Sembuh".
    """
    case = await case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(404, "case tidak ditemukan")

    try:
        updated = await case_service.confirm_case(
            db,
            case=case,
            confirmation=request.confirmation,
            confirmed_by=request.confirmed_by,
            confirmed_condition=request.confirmed_condition,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    if request.confirmation.value == "sakit" and not updated.medical_references:
        # Kasus tepi: penyakit yang dikonfirmasi di luar kandidat graph.
        updated.error = (
            "Belum ada data tindakan terverifikasi untuk kondisi ini; "
            "disarankan konsultasi manual dengan dokter hewan."
        )
    return updated
