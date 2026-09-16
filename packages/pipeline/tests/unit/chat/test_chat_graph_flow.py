from datetime import datetime

from langgraph.checkpoint.memory import InMemorySaver

from futechi_graphrag.infrastructure.checkpointer import get_checkpointer
from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate, GraphContext
from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry, CaseStore
from futechi_graphrag.pipelines.module_c_reasoning.dto import ChatMessage
from futechi_graphrag.pipelines.orchestration.chat_graph import (
    build_chat_graph,
    chat_config,
    summarize_cage_history,
)


def _candidate(name: str) -> DiseaseCandidate:
    return DiseaseCandidate(
        disease_id=f"id-{name}",
        disease_name=name,
        desc="",
        base_severity="medium",
        notifiable=False,
        matched_visual_features=[],
        related_symptoms=[],
        matched_environment=[],
        inspection_actions=[],
        mitigation_actions=[],
        medical_treatments=[],
    )


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        return f"jawaban-{len(self.prompts)}"


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def retrieve_context(self, **params) -> GraphContext:
        self.calls.append(params)
        return GraphContext(candidates=[_candidate("CRD"), _candidate("Infectious Coryza")])


def _ask(graph, case_id: str, question: str):
    return graph.invoke(
        {"case_id": case_id, "cage_id": "B40", "messages": [ChatMessage("user", question)]},
        config=chat_config(case_id),
    )


def test_two_turns_accumulate_messages_and_retrieve_every_turn() -> None:
    store = CaseStore()
    store.upsert_case(
        case_id="case-1",
        cage_id="B40",
        status="pending_confirmation",
        visual_features=["conjunctivitis"],
        environment_conditions=["ammonia_attention"],
    )
    store.upsert_case(case_id="case-0", cage_id="B40", status="CONFIRMED_SICK", confirmed_condition="Infectious Coryza")
    repository, llm = FakeRepository(), FakeLLM()
    graph = build_chat_graph(store, disease_repository=repository, llm_client=llm, checkpointer=InMemorySaver())

    _ask(graph, "case-1", "Q1")
    second = _ask(graph, "case-1", "Q2")

    assert [(m.role, m.content) for m in second["messages"]] == [
        ("user", "Q1"),
        ("assistant", "jawaban-1"),
        ("user", "Q2"),
        ("assistant", "jawaban-2"),
    ]
    assert repository.calls == [
        {"visual_features": ["conjunctivitis"], "environment_conditions": ["ammonia_attention"]}
    ] * 2
    assert "CATATAN RIWAYAT" in llm.prompts[0] and "confirmed_sick (Infectious Coryza)" in llm.prompts[0]
    assert "assistant: jawaban-1" in llm.prompts[1]


def test_status_update_between_turns_scopes_retrieval_to_confirmed_disease() -> None:
    store = CaseStore()
    store.upsert_case(case_id="case-2", cage_id="B40", status="pending_confirmation", visual_features=["conjunctivitis"])
    graph = build_chat_graph(store, disease_repository=FakeRepository(), llm_client=FakeLLM(), checkpointer=InMemorySaver())

    first = _ask(graph, "case-2", "Q1")
    store.upsert_case(case_id="case-2", cage_id="B40", status="confirmed_sick", confirmed_condition="Infectious Coryza")
    second = _ask(graph, "case-2", "Q2")

    assert len(first["graph_context"].candidates) == 2
    assert second["case_status"] == "confirmed_sick"
    assert [c.disease_name for c in second["graph_context"].candidates] == ["Infectious Coryza"]
    assert second["visual_features"] == ["conjunctivitis"]  # tidak hilang saat status diperbarui


def test_respond_is_skipped_without_llm_client() -> None:
    graph = build_chat_graph(CaseStore(), checkpointer=InMemorySaver())
    result = _ask(graph, "case-3", "Q1")
    assert [m.role for m in result["messages"]] == ["user"]


def test_checkpointer_is_shared_process_wide() -> None:
    assert get_checkpointer() is get_checkpointer()


def test_summarize_cage_history() -> None:
    assert summarize_cage_history([]) is None
    summary = summarize_cage_history(
        [CageHistoryEntry("c", datetime(2026, 9, 1), "confirmed_healthy")]
    )
    assert summary == "- 2026-09-01: confirmed_healthy"
