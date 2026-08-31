"""
Response statis untuk kasus graph_context kosong (boundary check gagal
di Modul B). TIDAK memanggil LLM sama sekali -- ini titik paling rawan
hallucination kalau dibiarkan generatif (tidak ada bukti graph sama
sekali untuk dijadikan pijakan), jadi responsnya sepenuhnya template
tetap.
"""
from futechi_graphrag.pipelines.module_c_reasoning.dto import ReasoningOutput


def build_insufficient_data_response() -> ReasoningOutput:
    return ReasoningOutput(
        related_conditions=[],
        recommended_checks=[],
        disease_actions={},
        severity=None,
        overall_uncertainty=(
            "Tidak ditemukan kecocokan kondisi terverifikasi di knowledge "
            "graph. Disarankan pemeriksaan manual menyeluruh."
        ),
        notifiable_notice=None,
    )
