"""
Orkestrasi utama Modul C -- dua fungsi entry point:

  - reason()            : Tier 1, dipanggil saat case baru dibuat
                           (diagnostic_graph).
  - reason_chat_turn()   : dipanggil tiap giliran chat lanjutan
                           (chat_graph) -- sync_case_state & load_cage_history
                           terjadi SEBELUM fungsi ini dipanggil.
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


def format_candidate_context(candidate: DiseaseCandidate) -> list[str]:
    """
    Blok konteks satu kandidat. Fitur visual yang COCOK dipisah tegas dari
    gejala terkait yang BELUM teramati, supaya LLM tidak memperlakukan
    gejala dari graph sebagai bukti.
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


def reason(
    case_context: CaseContextInput,
    graph_context: GraphContext,
    llm_client: LLMClient,
) -> ReasoningOutput:
    """
    Reasoning Tier 1 -- dipanggil saat case baru dibuat.

    Jika graph_context kosong, TIDAK memanggil LLM sama sekali --
    langsung fallback statis (lihat fallback_template.py).
    """
    if graph_context.is_empty():
        return build_insufficient_data_response()

    prompt = build_diagnostic_prompt(case_context, graph_context.candidates)
    llm_response = llm_client.generate_structured(
        system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
        user_prompt=prompt,
        schema=ReasoningLLMResponse,
    )

    # Catatan untuk nama di luar kandidat diabaikan (aturan: nama wajib persis).
    notes_by_disease = {
        item.disease_name: item.differential_note
        for item in llm_response.differential_notes
    }

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
        overall_uncertainty=llm_response.overall_uncertainty,
        notifiable_notice=build_notifiable_notice(graph_context.candidates),
    )


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
    if graph_context.is_empty():
        lines.append("(tidak ada data graph terverifikasi untuk konteks ini)")
    else:
        for candidate in graph_context.candidates:
            lines += format_candidate_context(candidate)

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
