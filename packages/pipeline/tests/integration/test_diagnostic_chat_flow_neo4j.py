"""
Integration test alur end-to-end dengan Neo4j sungguhan.
MLLM & LLM memakai fake (deterministik, tanpa biaya API) -- uji live LLM
dilakukan manual lewat scripts/smoke_llm.py dan scripts/demo_flow.py.
"""
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from futechi_graphrag.infrastructure.persistence.case_store import CaseStore
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    ExtractedFeature,
    FrameExtractionResponse,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    ChatMessage,
    DifferentialNoteItem,
    ReasoningLLMResponse,
)
from futechi_graphrag.pipelines.orchestration.chat_graph import build_chat_graph, chat_config
from futechi_graphrag.pipelines.orchestration.diagnostic_graph import (
    DiagnosticDependencies,
    build_diagnostic_graph,
    initial_diagnostic_state,
)

pytestmark = pytest.mark.integration


class StaticMLLM:
    def __init__(self, features: list[str]) -> None:
        self.features = features

    def generate_structured_with_images(self, system_prompt, user_prompt, images, schema):
        return FrameExtractionResponse(
            bird_visible=True,
            image_usable=True,
            features=[ExtractedFeature(name=name, confidence=0.9) for name in self.features],
        )


class EchoLLM:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate_structured(self, system_prompt, user_prompt, schema):
        self.prompts.append(user_prompt)
        return ReasoningLLMResponse(
            differential_notes=[
                DifferentialNoteItem(
                    disease_name="CRD (Mycoplasma gallisepticum)", differential_note="catatan uji"
                )
            ],
            overall_uncertainty="uji integrasi",
        )

    def generate(self, system_prompt, user_prompt):
        self.prompts.append(user_prompt)
        return "jawaban uji"


def _deps(features, disease_repository, ontology_repository, llm) -> DiagnosticDependencies:
    return DiagnosticDependencies(
        mllm_client=StaticMLLM(features),
        llm_client=llm,
        disease_repository=disease_repository,
        ontology_repository=ontology_repository,
    )


def test_diagnostic_graph_runs_against_real_graph(disease_repository, ontology_repository) -> None:
    llm = EchoLLM()
    graph = build_diagnostic_graph(
        _deps(["conjunctivitis", "nasal_discharge"], disease_repository, ontology_repository, llm)
    )

    result = graph.invoke(
        initial_diagnostic_state(
            case_id="IT-1",
            cage_id="B40",
            blok_id="Z3",
            crops=[b"a", b"b", b"c"],
            raw_environment={"temperature_c": 29.0, "humidity_percent": 70.0, "ammonia_ppm": 25.0},
        )
    )

    assert result["status"] == "completed"
    output = result["reasoning_output"]
    names = [condition.disease_name for condition in output.related_conditions]
    assert "CRD (Mycoplasma gallisepticum)" in names
    assert output.related_conditions[names.index("CRD (Mycoplasma gallisepticum)")].differential_note == "catatan uji"
    assert output.severity is not None
    assert output.notifiable_notice is None
    crd_actions = output.disease_actions["CRD (Mycoplasma gallisepticum)"]
    assert crd_actions.medical_references[0].treatment_name.startswith("[DUMMY]")
    assert "amonia 25.0ppm" in llm.prompts[0]


def test_diagnostic_graph_flags_notifiable_hpai(disease_repository, ontology_repository) -> None:
    graph = build_diagnostic_graph(
        _deps(["cyanotic_comb_wattle"], disease_repository, ontology_repository, EchoLLM())
    )
    result = graph.invoke(
        initial_diagnostic_state(case_id="IT-2", cage_id="B41", blok_id="Z3", crops=[b"a", b"b"])
    )
    assert "Avian Influenza H5 (HPAI)" in result["reasoning_output"].notifiable_notice


def test_chat_graph_scopes_real_retrieval_to_confirmed_disease(disease_repository) -> None:
    store = CaseStore()
    store.upsert_case(
        case_id="IT-3",
        cage_id="B40",
        status="confirmed_sick",
        confirmed_condition="Infectious Coryza",
        visual_features=["conjunctivitis", "nasal_discharge"],
        environment_conditions=[],
    )
    llm = EchoLLM()
    graph = build_chat_graph(
        store, disease_repository=disease_repository, llm_client=llm, checkpointer=InMemorySaver()
    )

    result = graph.invoke(
        {"case_id": "IT-3", "cage_id": "B40", "messages": [ChatMessage("user", "Apa yang harus dilakukan?")]},
        config=chat_config("IT-3"),
    )

    assert [c.disease_name for c in result["graph_context"].candidates] == ["Infectious Coryza"]
    assert result["messages"][-1] == ChatMessage("assistant", "jawaban uji")
    assert "[Infectious Coryza]" in llm.prompts[0]
    assert "[CRD (Mycoplasma gallisepticum)]" not in llm.prompts[0]
