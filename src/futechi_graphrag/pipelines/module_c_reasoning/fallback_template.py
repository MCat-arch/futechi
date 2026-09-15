"""
Response statis untuk kasus graph_context kosong (boundary check gagal
di Modul B) atau fitur tidak terpetakan. TIDAK memanggil LLM sama sekali --
ini titik paling rawan hallucination kalau dibiarkan generatif (tidak ada
bukti graph sama sekali untuk dijadikan pijakan), jadi responsnya
sepenuhnya template tetap, tetapi tetap actionable.
"""
from futechi_graphrag.domain.value_objects.observation import InspectionAction
from futechi_graphrag.pipelines.module_c_reasoning.dto import ReasoningOutput

FALLBACK_CHECKS: tuple[InspectionAction, ...] = (
    InspectionAction(
        name="general_visual_check",
        instruction=(
            "Periksa ulang ayam secara langsung: postur, mata, hidung, pernapasan, "
            "jengger, bulu sekitar kloaka, dan feses."
        ),
    ),
    InspectionAction(
        name="monitor_24h",
        instruction=(
            "Pantau ayam ini selama 24 jam: catat perubahan kondisi, konsumsi pakan "
            "dan minum, serta kematian di blok yang sama."
        ),
    ),
)


def build_insufficient_data_response() -> ReasoningOutput:
    return ReasoningOutput(
        related_conditions=[],
        recommended_checks=list(FALLBACK_CHECKS),
        disease_actions={},
        severity=None,
        overall_uncertainty=(
            "Tidak ditemukan kecocokan kondisi terverifikasi di knowledge "
            "graph. Disarankan pemeriksaan manual menyeluruh."
        ),
        notifiable_notice=None,
    )
