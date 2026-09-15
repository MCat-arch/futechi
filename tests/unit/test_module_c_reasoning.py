from futechi_graphrag.domain.value_objects.enums import SeverityLevel
from futechi_graphrag.domain.value_objects.observation import (
    EnvironmentSnapshot,
    VisualFeatureObservation,
)
from futechi_graphrag.infrastructure.neo4j.dto import (
    AttributedFeature,
    DiseaseCandidate,
    GraphContext,
    MatchedEnvironmentCondition,
    RawInspectionAction,
    RawMitigationAction,
)
from futechi_graphrag.pipelines.module_c_reasoning.deterministic_builders import (
    build_evidence_strings,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    CaseContextInput,
    ChatMessage,
    DifferentialNoteItem,
    ReasoningLLMResponse,
)
from futechi_graphrag.pipelines.module_c_reasoning.prompt_constraints import (
    CHAT_SYSTEM_PROMPT,
    DIAGNOSTIC_SYSTEM_PROMPT,
)
from futechi_graphrag.pipelines.module_c_reasoning.reasoner import (
    build_chat_prompt,
    build_diagnostic_prompt,
    reason,
    reason_chat_turn,
)


class FakeLLMClient:
    def __init__(self, structured=None, text: str = "jawaban") -> None:
        self.structured = structured
        self.text = text
        self.calls: list[dict] = []

    def generate_structured(self, system_prompt, user_prompt, schema):
        self.calls.append({"system": system_prompt, "user": user_prompt, "schema": schema})
        return self.structured

    def generate(self, system_prompt, user_prompt):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return self.text


CRD = DiseaseCandidate(
    disease_id="DIS-001",
    disease_name="CRD (Mycoplasma gallisepticum)",
    desc="",
    base_severity="medium",
    notifiable=False,
    condition_type="infectious_bacterial",
    validation_note="Mata cekung tidak khas CRD.",
    diagnostic_note="PCR real-time: sensitivitas ~65-80%.",
    matched_visual_features=[AttributedFeature("conjunctivitis", "low", None, None, "catatan konjungtivitis")],
    related_symptoms=[AttributedFeature("tracheal_rales", "low", None, None)],
    matched_environment=[MatchedEnvironmentCondition("ammonia_attention", "medium", "Amonia tinggi")],
    inspection_actions=[
        RawInspectionAction("observe_breathing", "Dengarkan napas"),
        RawInspectionAction("refer_pcr_test", "PCR"),
    ],
    mitigation_actions=[RawMitigationAction("isolate_affected_bird", "Pisahkan", "high")],
    medical_treatments=[],
)

HPAI = DiseaseCandidate(
    disease_id="DIS-009",
    disease_name="Avian Influenza H5 (HPAI)",
    desc="",
    base_severity="critical",
    notifiable=True,
    condition_type="infectious_viral",
    matched_visual_features=[AttributedFeature("cyanotic_comb_wattle", "high", None, None)],
    related_symptoms=[AttributedFeature("sudden_high_mortality", "high", "early", None)],
    matched_environment=[],
    inspection_actions=[RawInspectionAction("refer_pcr_test", "PCR")],
    mitigation_actions=[],
    medical_treatments=[],
)

CASE = CaseContextInput(
    cage_id="B40",
    blok_id="Z3",
    visual_features=[VisualFeatureObservation("conjunctivitis", 0.82)],
)


def test_empty_graph_context_uses_actionable_fallback_without_llm() -> None:
    client = FakeLLMClient()
    output = reason(CASE, GraphContext(candidates=[]), client)

    assert client.calls == []
    assert output.related_conditions == []
    assert [check.name for check in output.recommended_checks] == [
        "general_visual_check",
        "monitor_24h",
    ]
    assert output.severity is None


def test_reason_builds_output_from_graph_and_only_notes_from_llm() -> None:
    client = FakeLLMClient(
        ReasoningLLMResponse(
            differential_notes=[
                DifferentialNoteItem(disease_name=CRD.disease_name, differential_note="Lebih didukung."),
                DifferentialNoteItem(disease_name="Penyakit Karangan", differential_note="abaikan"),
            ],
            overall_uncertainty="tinggi",
        )
    )

    output = reason(CASE, GraphContext(candidates=[CRD, HPAI]), client)

    assert client.calls[0]["system"] == DIAGNOSTIC_SYSTEM_PROMPT
    assert client.calls[0]["schema"] is ReasoningLLMResponse
    names = [condition.disease_name for condition in output.related_conditions]
    assert names == [CRD.disease_name, HPAI.disease_name]
    assert output.related_conditions[0].differential_note == "Lebih didukung."
    assert "Tidak ada catatan diferensial" in output.related_conditions[1].differential_note
    assert [check.name for check in output.recommended_checks] == ["observe_breathing", "refer_pcr_test"]
    assert set(output.disease_actions) == {CRD.disease_name, HPAI.disease_name}
    assert output.overall_uncertainty == "tinggi"
    assert HPAI.disease_name in output.notifiable_notice

    # HPAI critical x early(1.0) = 4.0 (HIGH) > CRD medium x onset tidak diketahui(1.0) = 2.0
    assert output.severity.base_severity == "critical"
    assert output.severity.onset_stage == "early"
    assert output.severity.level == SeverityLevel.HIGH


def test_evidence_contains_only_observed_features_and_matched_environment() -> None:
    evidence = build_evidence_strings(CRD)
    assert evidence == [
        "conjunctivitis (low specificity)",
        "lingkungan: ammonia_attention (medium strength)",
    ]
    assert not any("tracheal_rales" in item for item in evidence)


def test_diagnostic_prompt_separates_observed_features_from_unobserved_symptoms() -> None:
    prompt = build_diagnostic_prompt(CASE, [CRD])

    assert "Kandang: B40, Blok: Z3" in prompt
    assert "Lingkungan: data sensor tidak tersedia" in prompt
    assert "- conjunctivitis (confidence: 0.82)" in prompt
    assert "gejala terkait (BELUM teramati" in prompt
    assert "tracheal_rales" in prompt
    assert "onset_stage=tidak diketahui" in prompt
    assert "catatan=catatan konjungtivitis" in prompt
    assert "jenis kondisi: infectious_bacterial" in prompt
    assert "catatan diagnostik: PCR real-time" in prompt


def test_diagnostic_prompt_includes_environment_snapshot_when_available() -> None:
    case = CaseContextInput(
        cage_id="B40",
        blok_id="Z3",
        visual_features=[],
        environment_snapshot=EnvironmentSnapshot(30.5, 76, 22, ("humidity_attention",)),
        capture_quality="low",
    )
    prompt = build_diagnostic_prompt(case, [])
    assert "suhu 30.5°C" in prompt
    assert "Kondisi perhatian: humidity_attention" in prompt
    assert "Kualitas capture: low" in prompt


def test_chat_turn_uses_chat_prompt_with_history_block() -> None:
    client = FakeLLMClient(text="Silakan periksa napas.")
    reply = reason_chat_turn(
        graph_context=GraphContext(candidates=[CRD]),
        cage_history_summary="Pernah CONFIRMED_SICK CRD 30 hari lalu",
        case_status="PENDING_CONFIRMATION",
        confirmed_disease=None,
        messages=[ChatMessage(role="user", content="Perlu apa?")],
        llm_client=client,
    )

    assert reply == "Silakan periksa napas."
    assert client.calls[0]["system"] == CHAT_SYSTEM_PROMPT
    assert "CATATAN RIWAYAT (informasional" in client.calls[0]["user"]
    assert "user: Perlu apa?" in client.calls[0]["user"]


def test_chat_prompt_reports_empty_graph_context() -> None:
    prompt = build_chat_prompt(GraphContext(candidates=[]), None, "CONFIRMED_SICK", "X", [])
    assert "(tidak ada data graph terverifikasi untuk konteks ini)" in prompt
    assert "Penyakit yang sudah dikonfirmasi: X" in prompt
