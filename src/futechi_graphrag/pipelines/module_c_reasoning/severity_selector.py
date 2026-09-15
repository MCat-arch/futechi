"""
Pilih severity final untuk case dari seluruh kandidat penyakit yang match.

PRINSIP: worst-case / precautionary -- sistem screening kesehatan lebih
baik terlalu waspada (over-alert) daripada meremehkan kasus yang
berpotensi serius, mengingat differential diagnosis PASTI masih perlu
konfirmasi manual. Karena itu:
  - Untuk tiap kandidat, dipilih onset_stage TERLAMBAT (late > middle >
    early) di antara visual_features/symptoms yang match. Jika tidak ada
    onset_stage sama sekali (sumber tidak menyebutkan), severity memakai
    base_severity dengan multiplier 1.0.
  - Severity akhir case = severity TERTINGGI di antara semua kandidat,
    bukan rata-rata atau severity kandidat "teratas" (sistem ini sengaja
    tidak punya ranking/skor kandidat).
"""
from futechi_graphrag.domain.value_objects.severity import (
    SeverityResult,
    compute_severity,
)
from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate

_ONSET_STAGE_ORDER = {"early": 0, "middle": 1, "late": 2}


def _worst_onset_stage(candidate: DiseaseCandidate) -> str | None:
    all_attrs = candidate.matched_visual_features + candidate.related_symptoms
    stages = [a.onset_stage for a in all_attrs if a.onset_stage in _ONSET_STAGE_ORDER]
    if not stages:
        return None
    return max(stages, key=lambda s: _ONSET_STAGE_ORDER[s])


def compute_case_severity(candidates: list[DiseaseCandidate]) -> SeverityResult | None:
    """
    Return None jika tidak ada kandidat, atau semua kandidat punya
    base_severity yang tidak dikenal (data KG bermasalah -- dilewati
    daripada crash seluruh case).
    """
    results: list[SeverityResult] = []

    for candidate in candidates:
        try:
            results.append(
                compute_severity(candidate.base_severity, _worst_onset_stage(candidate))
            )
        except ValueError:
            continue

    if not results:
        return None

    return max(results, key=lambda r: r.raw_score)
