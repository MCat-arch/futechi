from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate, GraphContext
from futechi_graphrag.pipelines.orchestration.chat_graph import apply_retrieval_scope
from futechi_graphrag.pipelines.orchestration.state import ChatState


def _candidate(name: str) -> DiseaseCandidate:
    return DiseaseCandidate(
        disease_id=f"id-{name}",
        disease_name=name,
        desc="",
        base_severity="high",
        notifiable=False,
        matched_visual_features=[],
        related_symptoms=[],
        matched_environment=[],
        inspection_actions=[],
        mitigation_actions=[],
        medical_treatments=[],
    )


candidate_a = _candidate("Newcastle Disease")
candidate_b = _candidate("Avian Influenza")


def test_pending_confirmation_keeps_multi_candidate_result() -> None:
    graph_context = GraphContext(candidates=[candidate_a, candidate_b])
    state = ChatState(
        case_id="case-1",
        cage_id="cage-1",
        case_status="pending_confirmation",
        confirmed_disease=None,
        graph_context=graph_context,
    )

    filtered = apply_retrieval_scope(state, state.graph_context)

    assert len(filtered.candidates) == 2
