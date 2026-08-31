"""
Orkestrasi utama Modul C -- dua fungsi entry point:

  - reason()            : Tier 1, dipanggil saat case baru dibuat
                           (diagnostic_graph, Tahap 8).
  - reason_chat_turn()   : dipanggil tiap giliran chat lanjutan
                           (chat_graph, Tahap 8) -- lihat Design Addendum
                           soal sync_case_state & load_cage_history yang
                           terjadi SEBELUM fungsi ini dipanggil (bukan di
                           dalam file ini).
"""
from futechi_graphrag.domain.value_objects.observation import RelatedCondition
from futechi_graphrag.infrastructure.llm.client import LLMClient
from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate, GraphContext
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


def build_diagnostic_prompt(
    case_context: CaseContextInput, candidates: list[DiseaseCandidate]
) -> str:
    """
    Susun teks konteks untuk LLM. SENGAJA tidak menyertakan riwayat
    kandang (Design Addendum Keputusan 3: riwayat HANYA di chat).
    """
    lines = [
        f"Kandang: {case_context.cage_id}, Zona: {case_context.zone_id}",
        "",
        "Fitur visual teramati:",
    ]
    for f in case_context.visual_features:
        lines.append(f"- {f.name} (confidence: {f.confidence:.2f})")

    lines.append("")
    lines.append(
        f"Lingkungan: suhu {case_context.environment_snapshot.temperature_c}°C, "
        f"kelembapan {case_context.environment_snapshot.humidity_percent}%, "
        f"amonia {case_context.environment_snapshot.ammonia_ppm}ppm"
    )
    if case_context.environment_snapshot.normalized_conditions:
        lines.append(
            "Kondisi perhatian: "
            + ", ".join(case_context.environment_snapshot.normalized_conditions)
        )

    lines.append("")
    lines.append("Kandidat penyakit dari knowledge graph:")
    for c in candidates:
        lines.append(f"\n[{c.disease_name}]")
        for feat in c.matched_visual_features + c.related_symptoms:
            lines.append(
                f"  - {feat.name}: specificity={feat.specificity}, "
                f"onset_stage={feat.onset_stage}, mechanism={feat.mechanism}"
            )
        for env in c.matched_environment:
            lines.append(f"  - lingkungan {env.name}: strength={env.strength}")

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
    eksplisit "informasional" -- sesuai Design Addendum Keputusan 3-4.
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
        for c in graph_context.candidates:
            lines.append(f"[{c.disease_name}]")
            for feat in c.matched_visual_features + c.related_symptoms:
                lines.append(
                    f"  - {feat.name}: specificity={feat.specificity}, "
                    f"onset_stage={feat.onset_stage}"
                )

    lines.append("")
    lines.append("RIWAYAT PERCAKAPAN:")
    for m in messages:
        lines.append(f"{m.role}: {m.content}")

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
    Reasoning untuk satu giliran chat -- mengembalikan teks bebas
    (bukan structured output seperti reason()), karena chat memang
    percakapan bebas. TETAP terikat hard constraint yang sama +
    rule #11 (riwayat kandang), lihat CHAT_SYSTEM_PROMPT.
    """
    prompt = build_chat_prompt(
        graph_context, cage_history_summary, case_status, confirmed_disease, messages
    )
    return llm_client.generate(system_prompt=CHAT_SYSTEM_PROMPT, user_prompt=prompt)
