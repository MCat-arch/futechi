"""
Celery worker — menjalankan diagnostic_graph di background.

Kenapa message queue, bukan BackgroundTasks biasa:
  - satu case butuh 10-40 detik (ekstraksi MLLM per crop + reasoning)
  - butuh retry saat endpoint LLM timeout / rate limit
  - API tetap responsif; edge cukup menerima case_id lalu polling

Catatan eksekusi: pipeline BERSIFAT SINKRON (driver neo4j & client OpenAI
sync), jadi graph dipanggil langsung di worker. Yang async hanya penyimpanan
DB, sehingga dibungkus asyncio.run.
"""

from __future__ import annotations

import asyncio
from typing import Any

from celery import Celery
from futechi_graphrag.pipelines.orchestration.diagnostic_graph import (
    initial_diagnostic_state,
)

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "futechi_api",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def process_case_task(
    self,
    case_id: str,
    cage_id: str,
    blok_id: str | None,
    image_paths: list[str],
    capture_quality: str = "high",
    raw_environment: dict | None = None,
    excluded_disease_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Jalankan diagnostic_graph untuk satu case lalu simpan hasilnya."""
    from app.core.pipeline import get_diagnostic_graph

    try:
        graph = get_diagnostic_graph()
        state = graph.invoke(
            initial_diagnostic_state(
                case_id=case_id,
                cage_id=cage_id,
                blok_id=blok_id or "",
                crops=image_paths,
                capture_quality=capture_quality,
                raw_environment=raw_environment,
                excluded_disease_ids=excluded_disease_ids or (),
            )
        )
    except Exception as exc:  # noqa: BLE001 -- semua kegagalan node ditangani sama
        if self.request.retries >= self.max_retries:
            asyncio.run(_persist_failure(case_id, f"{type(exc).__name__}: {exc}"))
            return {"case_id": case_id, "status": "failed", "error": str(exc)}
        raise self.retry(exc=exc)

    asyncio.run(_persist_state(case_id, state))
    return {
        "case_id": case_id,
        "status": state.get("status"),
        "requires_manual_review": bool(state.get("requires_manual_review")),
        "candidates": [
            condition.disease_name
            for condition in getattr(state.get("reasoning_output"), "related_conditions", [])
        ],
    }


async def _persist_state(case_id: str, state: dict[str, Any]) -> None:
    from app.core.database import task_session
    from app.services import case_service

    async with task_session() as db:
        await case_service.save_pipeline_result(db, case_id, state)
        await db.commit()


async def _persist_failure(case_id: str, error: str) -> None:
    from app.core.database import task_session
    from app.services import case_service

    async with task_session() as db:
        await case_service.mark_case_failed(db, case_id, error)
        await db.commit()
