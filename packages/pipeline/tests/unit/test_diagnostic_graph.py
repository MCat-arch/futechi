import pytest

from futechi_graphrag.infrastructure.neo4j.dto import (
    AttributedFeature,
    DiseaseCandidate,
    GraphContext,
    RawInspectionAction,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    ExtractedFeature,
    FrameExtractionResponse,
    OtherObservation,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    CaseContextInput,
    DifferentialNoteItem,
    ReasoningLLMResponse,
)
from futechi_graphrag.pipelines.module_c_reasoning.reasoner import (
    assemble_reasoning_output,
    generate_differential_notes,
)
from futechi_graphrag.pipelines.orchestration.diagnostic_graph import (
    DiagnosticDependencies,
    build_diagnostic_graph,
    environment_snapshot_from,
    initial_diagnostic_state,
)

ONTOLOGY = OntologyRepository()

CRD = DiseaseCandidate(
    disease_id="DIS-001",
    disease_name="CRD (Mycoplasma gallisepticum)",
    desc="",
    base_severity="medium",
    notifiable=False,
    matched_visual_features=[AttributedFeature("conjunctivitis", "low", None, None)],
    related_symptoms=[],
    matched_environment=[],
    inspection_actions=[RawInspectionAction("observe_breathing", "Dengarkan napas")],
    mitigation_actions=[],
    medical_treatments=[],
)
EMPTY = GraphContext(candidates=[])


class FakeMLLM:
    def __init__(self, frames: list[FrameExtractionResponse]) -> None:
        self.frames = list(frames)

    def generate_structured_with_images(self, system_prompt, user_prompt, images, schema):
        return self.frames.pop(0)


class FakeLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_structured(self, system_prompt, user_prompt, schema):
        self.prompts.append(user_prompt)
        return ReasoningLLMResponse(
            differential_notes=[DifferentialNoteItem(disease_name=CRD.disease_name, differential_note="catatan")],
            overall_uncertainty="sedang",
        )


class FakeRepository:
    def __init__(self, contexts: list[GraphContext]) -> None:
        self.contexts = list(contexts)
        self.calls: list[dict] = []

    def retrieve_context(self, **params) -> GraphContext:
        self.calls.append(params)
        return self.contexts.pop(0) if self.contexts else EMPTY


def _frame(features=(), others=()) -> FrameExtractionResponse:
    return FrameExtractionResponse(
        bird_visible=True,
        image_usable=True,
        features=[ExtractedFeature(name=n, confidence=c) for n, c in features],
        other_observations=[OtherObservation(label=l, confidence=c) for l, c in others],
    )


def _run(frames, contexts, raw_environment=None):
    llm = FakeLLM()
    repository = FakeRepository(contexts)
    deps = DiagnosticDependencies(
        mllm_client=FakeMLLM(frames),
        llm_client=llm,
        disease_repository=repository,
        ontology_repository=ONTOLOGY,
    )
    result = build_diagnostic_graph(deps).invoke(
        initial_diagnostic_state(
            case_id="C1",
            cage_id="B40",
            blok_id="Z3",
            crops=[b"img"] * len(frames),
            raw_environment=raw_environment,
        )
    )
    return result, repository, llm


def test_normal_path_reaches_reasoning_and_recommendation() -> None:
    result, repository, llm = _run(
        [_frame([("conjunctivitis", 0.9)])] * 3,
        [GraphContext(candidates=[CRD])],
        raw_environment={"temperature_c": 31.0, "humidity_percent": 80.0, "ammonia_ppm": 25.0},
    )

    assert result["status"] == "completed"
    assert repository.calls == [
        {
            "visual_features": ["conjunctivitis"],
            "environment_conditions": ["temperature_attention", "humidity_attention", "ammonia_attention"],
            "excluded_disease_ids": [],
        }
    ]
    assert result["reasoning_output"].related_conditions[0].differential_note == "catatan"
    assert result["retrieval_retry_count"] == 0
    assert "suhu 31.0°C" in llm.prompts[0]


def test_manual_review_path_skips_retrieval_and_llm() -> None:
    result, repository, llm = _run([_frame(), _frame(), _frame()], [])

    assert result["status"] == "manual_review"
    assert repository.calls == [] and llm.prompts == []
    assert [c.name for c in result["reasoning_output"].recommended_checks] == [
        "general_visual_check",
        "monitor_24h",
    ]


def test_empty_retrieval_retries_once_with_remapped_label() -> None:
    frame = _frame([("pale_comb", 0.9)], [("conjunctivitus", 0.9)])
    result, repository, _ = _run([frame] * 3, [EMPTY, GraphContext(candidates=[CRD])])

    assert result["status"] == "completed"
    assert result["retrieval_retry_count"] == 1
    assert [call["visual_features"] for call in repository.calls] == [
        ["pale_comb"],
        ["pale_comb", "conjunctivitis"],
    ]
    assert any("conjunctivitis" in note for note in result["notes"])


def test_empty_retrieval_without_unmapped_labels_goes_to_fallback() -> None:
    result, repository, llm = _run([_frame([("pale_comb", 0.9)])] * 2, [EMPTY])

    assert result["status"] == "insufficient_data"
    assert len(repository.calls) == 1 and llm.prompts == []


def test_retry_that_stays_empty_goes_to_fallback() -> None:
    frame = _frame([("pale_comb", 0.9)], [("conjunctivitus", 0.9)])
    result, repository, llm = _run([frame] * 2, [EMPTY, EMPTY])

    assert result["status"] == "insufficient_data"
    assert len(repository.calls) == 2 and llm.prompts == []


def test_partial_environment_is_not_sent_as_snapshot() -> None:
    _, _, llm = _run(
        [_frame([("conjunctivitis", 0.9)])],
        [GraphContext(candidates=[CRD])],
        raw_environment={"temperature_c": 31.0, "humidity_percent": None, "ammonia_ppm": 25.0},
    )
    assert "Lingkungan: data sensor tidak tersedia" in llm.prompts[0]
    assert environment_snapshot_from({"temperature_c": 1, "humidity_percent": 2, "ammonia_ppm": 3}, ["x"]).normalized_conditions == ("x",)


def test_assemble_without_llm_response_uses_default_notes() -> None:
    output = assemble_reasoning_output(GraphContext(candidates=[CRD]), None)
    assert "Tidak ada catatan diferensial" in output.related_conditions[0].differential_note
    assert output.overall_uncertainty is None


def test_generate_differential_notes_refuses_empty_graph() -> None:
    with pytest.raises(ValueError):
        generate_differential_notes(CaseContextInput("B40", "Z3", []), EMPTY, FakeLLM())
