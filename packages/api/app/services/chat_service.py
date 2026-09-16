"""
Chat lanjutan per case — dijalankan lewat `chat_graph` milik pipeline.

Perbedaan penting dari backend lama: jawaban TIDAK lagi dibuat dengan
memanggil LLM berbekal konteks DB seadanya. Setiap giliran melewati
sync_case_state -> load_cage_history -> retrieve -> respond, sehingga:
  - selalu ada retrieval graph ulang (jawaban tetap grounded)
  - cakupan kandidat dibatasi status case (CONFIRMED_SICK -> hanya penyakit itu)
  - mitigasi & obat hanya masuk prompt setelah konfirmasi "Sakit"
  - riwayat kandang jelas ditandai informasional

Postgres adalah sumber kebenaran percakapan. Riwayat dimuat dari DB lalu
dikirim utuh ke graph tiap giliran, jadi checkpointer LangGraph hanya dipakai
sebagai penampung sementara dalam satu pemanggilan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    ChatMessage as PipelineChatMessage,
)
from futechi_graphrag.pipelines.orchestration.chat_graph import (
    build_chat_graph,
    chat_config,
)
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.pipeline import get_diagnostic_dependencies
from app.models.case import Case, ChatMessage
from app.services import case_service

settings = get_settings()


class PreloadedCaseStore:
    """
    Adapter CaseStore untuk chat graph.

    Data case & riwayat kandang sudah dimuat lebih dulu secara async dari
    Postgres, sehingga node graph (yang sinkron) tidak pernah menyentuh DB.
    """

    def __init__(self, record: dict[str, Any], history: list[CageHistoryEntry]) -> None:
        self._record = record
        self._history = history

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        return self._record if self._record.get("case_id") == case_id else None

    def find_resolved_cases_by_cage(
        self,
        cage_id: str,
        exclude_case_id: str | None = None,
        limit: int = 5,
        since_days: int = 90,
    ) -> list[CageHistoryEntry]:
        return [
            entry for entry in self._history if entry.case_id != exclude_case_id
        ][:limit]


def _case_record(case: Case) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "cage_id": case.cage_id,
        "status": case.status.value,
        "confirmed_condition": case.confirmed_condition,
        "visual_features": [f["name"] for f in (case.visual_features or [])],
        "environment_conditions": list(case.environment_conditions or []),
    }


async def _cage_history(db: AsyncSession, case: Case) -> list[CageHistoryEntry]:
    since = datetime.now(timezone.utc) - timedelta(days=settings.cage_history_days)
    rows = await case_service.recent_resolved_cases(
        db,
        cage_id=case.cage_id,
        exclude_case_id=case.id,
        limit=settings.cage_history_limit,
        since=since,
    )
    return [
        CageHistoryEntry(
            case_id=row.id,
            resolved_at=row.resolved_at,
            outcome=row.status.value,
            confirmed_condition=row.confirmed_condition,
        )
        for row in rows
        if row.resolved_at is not None
    ]


async def handle_chat(
    db: AsyncSession, *, case: Case, message: str
) -> tuple[ChatMessage, list[str]]:
    """Satu giliran chat. Mengembalikan (pesan asisten, cakupan kandidat)."""
    await case_service.add_chat_message(db, case_id=case.id, role="user", content=message)

    history = await case_service.list_chat_messages(db, case.id)
    store = PreloadedCaseStore(_case_record(case), await _cage_history(db, case))
    dependencies = get_diagnostic_dependencies()

    graph = build_chat_graph(
        store,
        disease_repository=dependencies.disease_repository,
        llm_client=dependencies.llm_client,
        checkpointer=InMemorySaver(),
    )

    # Pipeline bersifat sinkron -> jangan blokir event loop.
    state = await run_in_threadpool(
        graph.invoke,
        {
            "case_id": case.id,
            "cage_id": case.cage_id,
            "messages": [
                PipelineChatMessage(role=row.role, content=row.content) for row in history
            ],
        },
        config=chat_config(case.id),
    )

    graph_context = state.get("graph_context")
    scope = [c.disease_name for c in graph_context.candidates] if graph_context else []

    messages = state.get("messages", [])
    if not messages or messages[-1].role != "assistant":
        raise RuntimeError("chat graph tidak menghasilkan jawaban asisten")

    assistant = await case_service.add_chat_message(
        db,
        case_id=case.id,
        role="assistant",
        content=messages[-1].content,
        graph_scope=scope,
    )
    return assistant, scope
