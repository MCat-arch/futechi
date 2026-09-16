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


candidate_x = _candidate("Newcastle Disease")


def test_confirmed_not_sick_return_empty() -> None:
    state = ChatState(
        case_id="case-1",
        cage_id="cage-1",
        case_status="confirmed_not_sick",
        confirmed_disease=None,
        graph_context=GraphContext(candidates=[candidate_x]),
    )

    filtered = apply_retrieval_scope(state, state.graph_context)

    assert filtered.is_empty()
