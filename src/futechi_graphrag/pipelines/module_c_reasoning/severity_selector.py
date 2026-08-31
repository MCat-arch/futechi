"""
Pilih severity final untuk case dari seluruh kandidat penyakit yang match.

PRINSIP: worst-case / precautionary -- sistem screening kesehatan lebih
baik terlalu waspada (over-alert) daripada meremehkan kasus yang
berpotensi serius, mengingat differential diagnosis PASTI masih perlu
konfirmasi manual. Karena itu:
  - Untuk tiap kandidat, dipilih onset_stage TERLAMBAT (late > middle >
    early) di antara visual_features/symptoms yang match -- bukan yang
    paling umum/representatif.
  - Severity akhir case = severity TERTINGGI di antara semua kandidat,
    bukan rata-rata atau severity kandidat "teratas" (karena sistem ini
    sengaja tidak punya ranking/skor kandidat -- lihat keputusan
    "scoring dihilangkan" sebelumnya).
"""
from futechi_graphrag.domain.value_objects.severity import (
    SeverityResult,
    compute_severity,
)
from futechi_graphrag.infrastructure.neo4j.dto import DiseaseCandidate

_ONSET_STAGE_ORDER = {"early": 0, "middle": 1, "late": 2}


def _worst_onset_stage(candidate: DiseaseCandidate) -> str | None:
    all_attrs = candidate.matched_visual_features + candidate.related_symptoms
    stages = [a.onset_stage for a in all_attrs if a.onset_stage]
    if not stages:
        return None
    return max(stages, key=lambda s: _ONSET_STAGE_ORDER.get(s, 0))


def compute_case_severity(candidates: list[DiseaseCandidate]) -> SeverityResult | None:
    """
    Return None jika tidak ada kandidat, atau tidak ada satu pun kandidat
    yang punya onset_stage valid untuk dihitung (kasus tepi yang sebaiknya
    jarang terjadi kalau seed data konsisten, tapi tidak boleh crash
    kalau terjadi).
    """
    results: list[SeverityResult] = []

    for candidate in candidates:
        worst_stage = _worst_onset_stage(candidate)
        if worst_stage is None:
            continue
        try:
            results.append(compute_severity(candidate.base_severity, worst_stage))
        except ValueError:
            # base_severity/onset_stage tidak dikenal enum -- data KG
            # bermasalah, lewati kandidat ini daripada crash seluruh case.
            continue

    if not results:
        return None

    return max(results, key=lambda r: r.raw_score)
