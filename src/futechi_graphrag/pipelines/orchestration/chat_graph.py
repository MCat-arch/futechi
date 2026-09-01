"""Chat orchestration for the continuation flow.

The active flow is intentionally split into two separate memory layers:
- checkpointer: stores messages keyed by thread_id = case_id
- case store: stores official case status and confirmation result

The entry node `sync_case_state` always reloads the latest state before the chat
retrieval and response node runs. This keeps chat responses consistent with
button-confirmed updates that happen outside the chat itself.
"""

from __future__ import annotations

from futechi_graphrag.infrastructure.checkpointer import get_checkpointer
from futechi_graphrag.infrastructure.persistence.case_store import CaseStore
from futechi_graphrag.pipelines.orchestration.state import ChatState


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

def build_chat_graph(case_store: CaseStore | None = None):
    """Build the state graph for the chat continuation flow.

    The order 
    )
    Build LangGraph chat flow dengan urutan yang benar:
    sync_case_state -> load_cage_history -> retrieve -> respond.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is expected in project env
        raise RuntimeError(
            "langgraph is required to build the chat graph orchestration."
        ) from exc

    graph = StateGraph(ChatState)
    graph.add_node("sync_case_state", lambda state: sync_case_state(state, case_store))
    graph.add_node("load_cage_history", lambda state: load_cage_history(state, case_store))
    graph.add_node("retrieve", lambda state: state)
    graph.add_node("respond", lambda state: state)
    graph.add_edge("sync_case_state", "load_cage_history")
    graph.add_edge("load_cage_history", "retrieve")
    graph.add_edge("retrieve", "respond")
    graph.add_edge("respond", END)
    graph.set_entry_point("sync_case_state")
    return graph.compile(checkpointer=get_checkpointer())
