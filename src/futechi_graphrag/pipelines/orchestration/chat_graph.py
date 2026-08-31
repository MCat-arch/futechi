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

    state.case_status = str(record.get("status") or state.case_status)
    state.confirmed_disease = (
        str(record.get("confirmed_condition"))
        if record.get("confirmed_condition") is not None
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
        state.cage_id,
        exclude_case_id=state.case_id,
        limit=limit,
        since_days=since_days,
    )
    return state


def build_chat_graph(case_store: CaseStore | None = None):
    """Build the state graph for the chat continuation flow.

    The order is intentionally fixed to match the Design Addendum:
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
