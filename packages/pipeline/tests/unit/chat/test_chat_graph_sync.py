from datetime import datetime

from langgraph.checkpoint.memory import InMemorySaver

from futechi_graphrag.infrastructure.persistence.case_store import CaseStore
from futechi_graphrag.pipelines.orchestration.chat_graph import (
    load_cage_history,
    build_chat_graph,
    sync_case_state,
)
from futechi_graphrag.pipelines.orchestration.state import ChatState

def test_chat_state_default_are_safe() -> None:
    state = ChatState(case_id="case-001", cage_id="cage-001")

    assert state.case_status == "pending_confirmation"
    assert state.confirmed_disease is None
    assert state.messages == []
    assert state.cage_history == []

def test_sync_case_state_refreshes_status_and_confirmed_disease() -> None:
    store = CaseStore()
    store.upsert_case(
        case_id="case-001",
        cage_id="cage-001",
        status="CONFIRMED_SICK",
        confirmed_condition="Newcastle Disease",
        resolved_at=datetime.utcnow(),
    )

    state = ChatState(
        case_id="case-001",
        cage_id="cage-001",
        case_status="pending_confirmation",
        confirmed_disease=None,
    )

    updated = sync_case_state(state, store)

    assert updated.case_status == "confirmed_sick"
    assert updated.confirmed_disease == "Newcastle Disease"

def test_sync_case_state_keeps_messages_intact() -> None:
    store = CaseStore()
    store.upsert_case(
        case_id="case-002",
        cage_id="cage-002",
        status="PENDING_CONFIRMATION",
        confirmed_condition=None,
        resolved_at=None,
    )

    state = ChatState(
        case_id="case-002",
        cage_id="cage-002",
        case_status="pending_confirmation",
        confirmed_disease=None,
        messages=[
            {"role": "user", "content": "Apakah saya butuh tindakan?"},
        ],
    )

    updated = sync_case_state(state, store)

    assert len(updated.messages) == 1
    assert updated.messages[0]["content"] == "Apakah saya butuh tindakan?"

def test_load_cage_history_returns_recent_resolved_cases() -> None:
    store = CaseStore()
    for case_id, cage_id, status, condition in [
        ("case-010", "cage-100", "CONFIRMED_SICK", "Avian Influenza"),
        ("case-011", "cage-100", "confirmed_healthy", None),
        ("case-012", "cage-101", "CONFIRMED_SICK", "Other Disease"),
        ("case-013", "cage-100", "CONFIRMED_NOT_SICK", None),
        ("case-014", "cage-100", "pending_confirmation", None),
    ]:
        store.upsert_case(case_id=case_id, cage_id=cage_id, status=status, confirmed_condition=condition)

    state = ChatState(
        case_id="case-010",
        cage_id="cage-100",
        case_status="confirmed_sick",
        confirmed_disease="Avian Influenza",
    )

    updated = load_cage_history(state, store, limit=5, since_days=90)

    # status huruf besar kini ikut terhitung (B5); case sendiri & case pending tidak
    assert {item.case_id for item in updated.cage_history} == {"case-011", "case-013"}

def test_build_chat_graph_compiles_with_checkpointer() -> None:
    graph = build_chat_graph(checkpointer=InMemorySaver())

    assert graph is not None

    # optional smoke test: ensure graph can run with a thread config
    result = graph.invoke(
        {
            "case_id": "case-900",
            "cage_id": "cage-900",
            "messages": [],
        },
        config={"configurable": {"thread_id": "case-900"}},
    )

    assert result["case_id"] == "case-900"
