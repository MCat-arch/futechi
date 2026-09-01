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