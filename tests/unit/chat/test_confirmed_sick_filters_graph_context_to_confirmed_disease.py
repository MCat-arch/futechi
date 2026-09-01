def test_confirmed_sick_filters_graph_context_to_confirmed_disease() -> None:
    graph_context = GraphContext(
        candidates=[
            DiseaseCandidate(
                disease_id="d1",
                disease_name="Newcastle Disease",
                desc="",
                base_severity="high",
                notifiable=True,
                matched_visual_features=[],
                related_symptoms=[],
                matched_environment=[],
                inspection_actions=[],
                mitigation_actions=[],
                medical_treatments=[],
            ),
            DiseaseCandidate(
                disease_id="d2",
                disease_name="Avian Influenza",
                desc="",
                base_severity="high",
                notifiable=True,
                matched_visual_features=[],
                related_symptoms=[],
                matched_environment=[],
                inspection_actions=[],
                mitigation_actions=[],
                medical_treatments=[],
            ),
        ]
    )

    state = ChatState(
        case_id="case-1",
        cage_id="cage-1",
        case_status="confirmed_sick",
        confirmed_disease="Newcastle Disease",
        graph_context=graph_context,
    )

    filtered = apply_retrieval_scope(state, state.graph_context)

    assert len(filtered.candidates) == 1
    assert filtered.candidates[0].disease_name == "Newcastle Disease"