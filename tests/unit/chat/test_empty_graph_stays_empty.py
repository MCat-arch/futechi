def test_empty_graph_context_stays_empty() -> None:
    state = ChatState(
        case_id="case-1",
        cage_id="cage-1",
        case_status="confirmed_sick",
        confirmed_disease="Newcastle Disease",
        graph_context=GraphContext(candidates=[]),
    )

    filtered = apply_retrieval_scope(state, state.graph_context)
    assert filtered.is_empty()