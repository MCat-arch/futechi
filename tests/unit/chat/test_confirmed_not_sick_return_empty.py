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