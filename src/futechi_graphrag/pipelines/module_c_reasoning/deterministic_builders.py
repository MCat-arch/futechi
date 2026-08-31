"""
Builder DETERMINISTIK -- membangun sebagian besar output Modul C LANGSUNG
dari GraphContext, TANPA melibatkan LLM sama sekali.

Ini keputusan desain inti Tahap 7: evidence, recommended_checks,
mitigasi, dan referensi obat adalah FAKTA dari knowledge graph, bukan
sesuatu yang perlu "ditulis ulang" LLM. Meminimalkan permukaan
hallucination sedapat mungkin -- LLM HANYA dipakai untuk
differential_note & overall_uncertainty (lihat reasoner.py).
"""
from futechi_graphrag.domain.value_objects.observation import (
    DiseaseActionBundle,
    InspectionAction,
    MedicalReference,
    MitigationAction,
)
from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate


def build_evidence_strings(candidate: DiseaseCandidate) -> list[str]:
    """
    Bangun daftar evidence yang bisa dibaca manusia dari fitur/gejala
    yang match, lengkap dengan specificity & onset_stage -- format PERSIS
    seperti contoh di desain awal:
    "lowered_head_posture (high specificity, early stage)"
    """
    evidence: list[str] = []
    for feature in candidate.matched_visual_features:
        parts = []
        if feature.specificity:
            parts.append(f"{feature.specificity} specificity")
        if feature.onset_stage:
            parts.append(f"{feature.onset_stage} stage")
        suffix = f" ({', '.join(parts)})" if parts else ""
        evidence.append(f"{feature.name}{suffix}")

    for symptom in candidate.related_symptoms:
        parts = []
        if symptom.specificity:
            parts.append(f"{symptom.specificity} specificity")
        if symptom.onset_stage:
            parts.append(f"{symptom.onset_stage} stage")
        suffix = f" ({', '.join(parts)})" if parts else ""
        evidence.append(f"{symptom.name}{suffix}")

    return evidence


def build_unique_inspection_actions(
    candidates: list[DiseaseCandidate],
) -> list[InspectionAction]:
    """
    Gabungkan (union) semua InspectionAction dari SEMUA kandidat,
    deduplikasi berdasarkan nama -- supaya user tidak melihat instruksi
    yang sama berulang kali kalau beberapa kandidat sama-sama
    merekomendasikan pemeriksaan yang sama.
    """
    seen: dict[str, InspectionAction] = {}
    for candidate in candidates:
        for action in candidate.inspection_actions:
            if action.name not in seen:
                seen[action.name] = InspectionAction(
                    name=action.name,
                    instruction=action.instruction or "",
                )
    return list(seen.values())


def build_disease_action_bundles(
    candidates: list[DiseaseCandidate],
) -> dict[str, DiseaseActionBundle]:
    """
    Bangun mitigasi + referensi obat PER kandidat penyakit -- disimpan
    utuh (tidak digabung/dedup lintas kandidat, beda dari
    build_unique_inspection_actions) karena ini nanti "dibuka" secara
    SPESIFIK per penyakit yang dikonfirmasi user (lihat Case.resolve()
    di Tahap 2, two-stage reveal).
    """
    bundles: dict[str, DiseaseActionBundle] = {}
    for candidate in candidates:
        mitigations = tuple(
            MitigationAction(
                name=m.name,
                instruction=m.instruction or "",
                priority=m.priority or "medium",
            )
            for m in candidate.mitigation_actions
        )
        medical_references = tuple(
            MedicalReference(
                for_condition=candidate.disease_name,
                treatment_name=mt.name,
                dosage=mt.dosage or "Tidak tersedia -- konsultasikan dosis ke dokter hewan",
                withdrawal_period=mt.withdrawal_period or "Tidak berlaku",
            )
            for mt in candidate.medical_treatments
        )
        bundles[candidate.disease_name] = DiseaseActionBundle(
            disease_name=candidate.disease_name,
            mitigations=mitigations,
            medical_references=medical_references,
        )
    return bundles


def build_notifiable_notice(candidates: list[DiseaseCandidate]) -> str | None:
    """
    Bangun peringatan WAJIB LAPOR jika ada kandidat dengan flag
    `notifiable=True` (mis. Avian Influenza) -- DETERMINISTIK dari
    property Disease di graph, TIDAK PERNAH digenerate LLM mengingat
    ini menyangkut kepatuhan hukum/keselamatan yang tidak boleh
    tergantung pada "kepatuhan" model terhadap instruksi.
    """
    notifiable_names = [c.disease_name for c in candidates if c.notifiable]
    if not notifiable_names:
        return None

    names_str = ", ".join(notifiable_names)
    return (
        f"PERHATIAN: {names_str} adalah penyakit wajib lapor. "
        f"Jika dikonfirmasi, segera hubungi otoritas kesehatan hewan "
        f"setempat sesuai regulasi yang berlaku."
    )
