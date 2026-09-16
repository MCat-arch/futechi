"""
Orkestrasi utama Modul C.

Diagnostic (Tier 1) dipecah menjadi dua langkah supaya bisa menjadi dua node
LangGraph terpisah:
  - generate_differential_notes() : N5, SATU-SATUNYA langkah generatif (LLM)
  - assemble_reasoning_output()   : N6, deterministik dari graph (tanpa LLM)
  - reason()                      : gabungan keduanya (+ fallback graph kosong)

Chat:
  - reason_chat_turn()            : dipanggil tiap giliran chat lanjutan
                                    (sync_case_state & load_cage_history terjadi
                                    SEBELUM fungsi ini dipanggil).
"""
from futechi_graphrag.domain.value_objects.observation import (
    EnvironmentSnapshot,
    RelatedCondition,
)
from futechi_graphrag.infrastructure.llm.client import LLMClient
from futechi_graphrag.infrastructure.neo4j.dto import (
    AttributedFeature,
    DiseaseCandidate,
    GraphContext,
)
from futechi_graphrag.pipelines.module_c_reasoning.deterministic_builders import (
    build_disease_action_bundles,
    build_evidence_strings,
    build_notifiable_notice,
    build_unique_inspection_actions,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    CaseContextInput,
    ChatMessage,
    ReasoningLLMResponse,
    ReasoningOutput,
)
from futechi_graphrag.pipelines.module_c_reasoning.fallback_template import (
    build_insufficient_data_response,
)
from futechi_graphrag.pipelines.module_c_reasoning.prompt_constraints import (
    CHAT_SYSTEM_PROMPT,
    DIAGNOSTIC_SYSTEM_PROMPT,
)
from futechi_graphrag.pipelines.module_c_reasoning.severity_selector import (
    compute_case_severity,
)

_DEFAULT_DIFFERENTIAL_NOTE = "Tidak ada catatan diferensial tersedia dari LLM untuk kandidat ini."


def _format_attributed_feature(feature: AttributedFeature) -> str:
    parts = [
        f"specificity={feature.specificity or 'tidak diketahui'}",
        f"onset_stage={feature.onset_stage or 'tidak diketahui'}",
    ]
    if feature.mechanism:
        parts.append(f"mechanism={feature.mechanism}")
    if feature.clinical_note:
        parts.append(f"catatan={feature.clinical_note}")
    return f"{feature.name}: " + ", ".join(parts)


def format_candidate_context(
    candidate: DiseaseCandidate,
    *,
    include_inspections: bool = False,
    include_treatment: bool = False,
) -> list[str]:
    """
    Blok konteks satu kandidat. Fitur visual yang COCOK dipisah tegas dari
    gejala terkait yang BELUM teramati, supaya LLM tidak memperlakukan
    gejala dari graph sebagai bukti.

    include_inspections : sertakan InspectionAction (dipakai chat)
    include_treatment   : sertakan mitigasi + referensi obat -- HANYA untuk
                          penyakit yang sudah dikonfirmasi (Tahap 2 reveal)
    """
    lines = [f"[{candidate.disease_name}]"]
    if candidate.condition_type:
        lines.append(f"  jenis kondisi: {candidate.condition_type}")

    lines.append("  fitur visual yang cocok dengan observasi:")
    lines += [
        f"    - {_format_attributed_feature(feature)}"
        for feature in candidate.matched_visual_features
    ] or ["    - (tidak ada)"]

    if candidate.related_symptoms:
        lines.append("  gejala terkait (BELUM teramati, perlu pemeriksaan manual):")
        lines += [
            f"    - {_format_attributed_feature(symptom)}"
            for symptom in candidate.related_symptoms
        ]

    for env in candidate.matched_environment:
        note = f", catatan={env.note}" if env.note else ""
        lines.append(f"  lingkungan cocok: {env.name} (strength={env.strength}{note})")

    if candidate.validation_note:
        lines.append(f"  catatan validasi: {candidate.validation_note}")
    if candidate.diagnostic_note:
        lines.append(f"  catatan diagnostik: {candidate.diagnostic_note}")

    if include_inspections and candidate.inspection_actions:
        lines.append("  pemeriksaan yang disarankan (dari graph):")
        lines += [
            f"    - {action.name}: {action.instruction or '-'}"
            for action in candidate.inspection_actions
        ]

    if include_treatment:
        if candidate.mitigation_actions:
            lines.append("  mitigasi (dari graph):")
            lines += [
                f"    - {action.name} [prioritas {action.priority or '-'}]: {action.instruction or '-'}"
                for action in candidate.mitigation_actions
            ]
        if candidate.medical_treatments:
            lines.append("  referensi obat (dari graph, WAJIB di bawah pengawasan dokter hewan):")
            lines += [
                f"    - {treatment.name}: dosis={treatment.dosage or 'tidak tersedia'}, "
                f"withdrawal_period={treatment.withdrawal_period or 'tidak tersedia'}"
                for treatment in candidate.medical_treatments
            ]
    return lines


def _format_environment(snapshot: EnvironmentSnapshot | None) -> list[str]:
    if snapshot is None:
        return ["Lingkungan: data sensor tidak tersedia"]
    lines = [
        f"Lingkungan: suhu {snapshot.temperature_c}°C, "
        f"kelembapan {snapshot.humidity_percent}%, "
        f"amonia {snapshot.ammonia_ppm}ppm"
    ]
    if snapshot.normalized_conditions:
        lines.append("Kondisi perhatian: " + ", ".join(snapshot.normalized_conditions))
    return lines


def build_diagnostic_prompt(
    case_context: CaseContextInput, candidates: list[DiseaseCandidate]
) -> str:
    """
    Susun teks konteks untuk LLM. SENGAJA tidak menyertakan riwayat
    kandang (riwayat HANYA di chat).
    """
    lines = [
        f"Kandang: {case_context.cage_id}, Blok: {case_context.blok_id}",
        f"Kualitas capture: {case_context.capture_quality}",
        "",
        "Fitur visual teramati:",
    ]
    lines += [
        f"- {feature.name} (confidence: {feature.confidence:.2f})"
        for feature in case_context.visual_features
    ] or ["- (tidak ada)"]

    lines.append("")
    lines += _format_environment(case_context.environment_snapshot)

    lines.append("")
    lines.append("Kandidat kondisi dari knowledge graph:")
    for candidate in candidates:
        lines.append("")
        lines += format_candidate_context(candidate)

    return "\n".join(lines)


def generate_differential_notes(
    case_context: CaseContextInput,
    graph_context: GraphContext,
    llm_client: LLMClient,
) -> ReasoningLLMResponse:
    """N5 -- satu-satunya langkah generatif. Tidak boleh dipanggil untuk graph kosong."""
    if graph_context.is_empty():
        raise ValueError("graph_context kosong: gunakan fallback template, bukan LLM")

    return llm_client.generate_structured(
        system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
        user_prompt=build_diagnostic_prompt(case_context, graph_context.candidates),
        schema=ReasoningLLMResponse,
    )


def assemble_reasoning_output(
    graph_context: GraphContext,
    llm_response: ReasoningLLMResponse | None,
) -> ReasoningOutput:
    """
    N6 -- bangun output dari graph secara deterministik, lalu tempelkan
    catatan diferensial LLM (jika ada). Catatan untuk nama di luar kandidat
    diabaikan (aturan: nama wajib persis).
    """
    notes_by_disease = (
        {item.disease_name: item.differential_note for item in llm_response.differential_notes}
        if llm_response is not None
        else {}
    )

    related_conditions = [
        RelatedCondition(
            disease_name=candidate.disease_name,
            evidence=tuple(build_evidence_strings(candidate)),
            differential_note=notes_by_disease.get(
                candidate.disease_name, _DEFAULT_DIFFERENTIAL_NOTE
            ),
        )
        for candidate in graph_context.candidates
    ]

    return ReasoningOutput(
        related_conditions=related_conditions,
        recommended_checks=build_unique_inspection_actions(graph_context.candidates),
        disease_actions=build_disease_action_bundles(graph_context.candidates),
        severity=compute_case_severity(graph_context.candidates),
        overall_uncertainty=llm_response.overall_uncertainty if llm_response else None,
        notifiable_notice=build_notifiable_notice(graph_context.candidates),
    )


def reason(
    case_context: CaseContextInput,
    graph_context: GraphContext,
    llm_client: LLMClient,
) -> ReasoningOutput:
    """
    Reasoning Tier 1 lengkap (N5 + N6).

    Jika graph_context kosong, TIDAK memanggil LLM sama sekali --
    langsung fallback statis (lihat fallback_template.py).
    """
    if graph_context.is_empty():
        return build_insufficient_data_response()

    llm_response = generate_differential_notes(case_context, graph_context, llm_client)
    return assemble_reasoning_output(graph_context, llm_response)


def build_chat_prompt(
    graph_context: GraphContext,
    cage_history_summary: str | None,
    case_status: str,
    confirmed_disease: str | None,
    messages: list[ChatMessage],
) -> str:
    """
    Susun prompt untuk satu giliran chat. Riwayat kandang (jika ada)
    ditulis sebagai blok TERPISAH dari graph context, diberi label
    eksplisit "informasional".
    """
    lines = [f"Status case saat ini: {case_status}"]
    if confirmed_disease:
        lines.append(f"Penyakit yang sudah dikonfirmasi: {confirmed_disease}")

    if cage_history_summary:
        lines.append("")
        lines.append("CATATAN RIWAYAT (informasional, BUKAN bukti diagnostik utama):")
        lines.append(cage_history_summary)

    lines.append("")
    lines.append("BUKTI SAAT INI (dasar utama diagnosis):")
    # Mitigasi & obat hanya dibuka setelah konfirmasi "Sakit" (sejalan dengan Case.resolve()).
    reveal_treatment = case_status.strip().lower() == "confirmed_sick"
    if graph_context.is_empty():
        lines.append("(tidak ada data graph terverifikasi untuk konteks ini)")
    else:
        for candidate in graph_context.candidates:
            lines += format_candidate_context(
                candidate, include_inspections=True, include_treatment=reveal_treatment
            )

    lines.append("")
    lines.append("RIWAYAT PERCAKAPAN:")
    if not messages:
        lines.append("(tidak ada riwayat percakapan)")
    else:
        for message in messages:
            lines.append(f"{message.role}: {message.content}")

    return "\n".join(lines)


def reason_chat_turn(
    graph_context: GraphContext,
    cage_history_summary: str | None,
    case_status: str,
    confirmed_disease: str | None,
    messages: list[ChatMessage],
    llm_client: LLMClient,
) -> str:
    """
    Reasoning untuk satu giliran chat selalu menjaga:
    - graph_context = evidence utama
    - cage_history = catatan informasional
    - case_status dan confirmed_disease = konteks status
    """
    prompt = build_chat_prompt(
        graph_context=graph_context,
        cage_history_summary=cage_history_summary,
        case_status=case_status,
        confirmed_disease=confirmed_disease,
        messages=messages,
    )
    return llm_client.generate(system_prompt=CHAT_SYSTEM_PROMPT, user_prompt=prompt)
