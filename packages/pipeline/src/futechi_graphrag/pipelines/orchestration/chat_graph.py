"""Chat orchestration for the continuation flow.

Dua lapis memori yang sengaja dipisah:
- checkpointer : menyimpan `messages` per thread_id = case_id
- CaseStore    : sumber kebenaran status case, penyakit terkonfirmasi, dan
                 fitur visual/lingkungan case (bahan retrieval ulang)

Urutan node: sync_case_state -> load_cage_history -> retrieve -> respond.
Setiap giliran melakukan retrieval graph ulang (grounded), lalu cakupannya
dibatasi sesuai status case (apply_retrieval_scope).

Dependency (CaseStore, repository, LLM client, checkpointer) di-inject dan
dibuat SEKALI oleh aplikasi -- jangan membuat instance baru per request.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from futechi_graphrag.infrastructure.checkpointer import get_checkpointer
from futechi_graphrag.infrastructure.llm.client import LLMClient
from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry, CaseStore
from futechi_graphrag.pipelines.module_c_reasoning.dto import ChatMessage
from futechi_graphrag.pipelines.module_c_reasoning.reasoner import reason_chat_turn
from futechi_graphrag.pipelines.orchestration.state import ChatState

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver


def chat_config(case_id: str) -> dict[str, Any]:
    """Config invoke LangGraph: satu thread percakapan per case."""
    return {"configurable": {"thread_id": case_id}}


def sync_case_state(
    state: ChatState,
    case_store: CaseStore | None = None,
) -> ChatState:
    """Synchronize the mutable case status before any chat response is built."""
    store = case_store or CaseStore()
    record = store.get_case(state.case_id)
    if record is None:
        return state

    #ambil status yang paling baru dari source of truth (CaseStore) untuk memastikan konsistensi dengan update yang dilakukan di luar chat
    raw_status = record.get("status")
    if raw_status is not None:
        state.case_status = str(raw_status)
    #ambil confirmed disease terbaru
    confirmed_condition = record.get("confirmed_condition")
    state.confirmed_disease = (
        str(confirmed_condition)
        if confirmed_condition is not None
        else None
    )
    state.visual_features = list(record.get("visual_features") or [])
    state.environment_conditions = list(record.get("environment_conditions") or [])
    return state


def load_cage_history(
    state: ChatState,
    case_store: CaseStore | None = None,
    *,
    limit: int = 5,
    since_days: int = 90,
) -> ChatState:
    """Attach a short informational history of recent resolved cases for this cage."""
    store = case_store or CaseStore()
    state.cage_history = store.find_resolved_cases_by_cage(
        cage_id=state.cage_id,
        exclude_case_id=state.case_id,
        limit=limit,
        since_days=since_days,
    )
    return state

def apply_retrieval_scope(
    state: ChatState,
    graph_context: GraphContext | None,
) -> GraphContext :
    """membatasi / fokus ke candidate retrieval berdasarkan status case
    """
    if graph_context is None:
        return GraphContext(candidates=[])

    status = str(state.case_status or "").strip().lower()

    if status == "confirmed_sick":
        confirmed_name = str(state.confirmed_disease or "").strip()
        if not confirmed_name:
            return GraphContext(candidates=[])

        filtered = [
            candidate
            for candidate in graph_context.candidates
            if candidate.disease_name.strip().lower() == confirmed_name.lower()
        ]
        return GraphContext(candidates=filtered)

    if status in {"confirmed_not_sick", "confirmed_healthy"}:
        return GraphContext(candidates=[])
    return graph_context

def retrieve_conditional(
    state: ChatState,
    graph_context: GraphContext | None = None,
) -> ChatState:
    """retrive graph context hanya jika case status belum confirmed, atau jika sudah confirmed tapi tidak ada confirmed disease"""
    resolved_context = graph_context if graph_context is not None else state.graph_context
    state.graph_context = apply_retrieval_scope(state, resolved_context)
    return state


def summarize_cage_history(entries: Sequence[CageHistoryEntry]) -> str | None:
    """Ringkasan teks riwayat kandang untuk prompt chat (informasional)."""
    if not entries:
        return None
    lines = []
    for entry in entries:
        condition = f" ({entry.confirmed_condition})" if entry.confirmed_condition else ""
        lines.append(f"- {entry.resolved_at:%Y-%m-%d}: {entry.outcome}{condition}")
    return "\n".join(lines)


def to_chat_message(message: ChatMessage | Mapping[str, Any]) -> ChatMessage:
    if isinstance(message, ChatMessage):
        return message
    return ChatMessage(role=message["role"], content=message["content"])


def build_chat_graph(
    case_store: CaseStore | None = None,
    *,
    disease_repository: DiseaseRepository | None = None,
    llm_client: LLMClient | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
):
    """
    Build LangGraph chat flow: sync_case_state -> load_cage_history -> retrieve -> respond.

    - disease_repository None : retrieval ulang dilewati, memakai graph_context di state
    - llm_client None         : node respond tidak menambahkan jawaban
    - checkpointer None       : memakai saver bersama dari get_checkpointer()
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is expected in project env
        raise RuntimeError(
            "langgraph is required to build the chat graph orchestration."
        ) from exc

    store = case_store or CaseStore()

    def sync_node(state: ChatState) -> dict[str, Any]:
        synced = sync_case_state(state, store)
        return {
            "case_status": synced.case_status,
            "confirmed_disease": synced.confirmed_disease,
            "visual_features": synced.visual_features,
            "environment_conditions": synced.environment_conditions,
        }

    def history_node(state: ChatState) -> dict[str, Any]:
        return {"cage_history": load_cage_history(state, store).cage_history}

    def retrieve_node(state: ChatState) -> dict[str, Any]:
        context = state.graph_context
        if disease_repository is not None and state.visual_features:
            context = disease_repository.retrieve_context(
                visual_features=list(state.visual_features),
                environment_conditions=list(state.environment_conditions),
            )
        return {"graph_context": apply_retrieval_scope(state, context)}

    def respond_node(state: ChatState) -> dict[str, Any]:
        messages = [to_chat_message(message) for message in state.messages]
        if llm_client is None or not messages or messages[-1].role != "user":
            return {}
        reply = reason_chat_turn(
            graph_context=state.graph_context or GraphContext(candidates=[]),
            cage_history_summary=summarize_cage_history(state.cage_history),
            case_status=state.case_status,
            confirmed_disease=state.confirmed_disease,
            messages=messages,
            llm_client=llm_client,
        )
        return {"messages": [ChatMessage(role="assistant", content=reply)]}

    graph = StateGraph(ChatState)
    graph.add_node("sync_case_state", sync_node)
    graph.add_node("load_cage_history", history_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("respond", respond_node)
    graph.add_edge("sync_case_state", "load_cage_history")
    graph.add_edge("load_cage_history", "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)
    graph.set_entry_point("sync_case_state")
    return graph.compile(checkpointer=checkpointer or get_checkpointer())
