"""
Perhitungan severity dinamis.

Sesuai keputusan desain: severity TIDAK diambil langsung dari field statis
di node Disease, tapi dihitung ulang per-case dari kombinasi:

    severity(case) = base_severity(disease) x onset_stage_multiplier

base_severity datang dari Neo4j (statis, mencerminkan bahaya intrinsik
penyakit tsb). onset_stage datang dari atribut relasi HAS_VISUAL_FEATURE/
HAS_SYMPTOM yang paling relevan pada deteksi saat ini (dinamis per-case).

File ini TIDAK melakukan I/O apa pun -- murni fungsi kalkulasi, supaya
gampang di-unit-test dan gampang dikalibrasi ulang setelah pilot deployment
tanpa menyentuh bagian sistem lain.
"""
from dataclasses import dataclass

from poultry_graphrag.domain.value_objects.enums import SeverityLevel

# Bobot pengali per tahap onset. Nilai awal (belum divalidasi vet) --
# WAJIB dikalibrasi ulang setelah pilot deployment.
ONSET_STAGE_MULTIPLIER: dict[str, float] = {
    "early": 1.0,
    "middle": 1.5,
    "late": 2.0,
}

# Skor dasar numerik per level severity, dipakai untuk menghitung skor
# gabungan sebelum dipetakan balik ke SeverityLevel.
BASE_SEVERITY_SCORE: dict[str, float] = {
    "low": 1.0,
    "medium": 2.0,
    "high": 3.0,
    "critical": 4.0,
}

# Batas ambang untuk memetakan skor gabungan balik ke SeverityLevel.
# Urutan dari batas TERTINGGI ke TERENDAH -- fungsi _score_to_level()
# bergantung pada urutan ini.
SEVERITY_SCORE_THRESHOLDS: list[tuple[float, SeverityLevel]] = [
    (6.0, SeverityLevel.CRITICAL),
    (4.0, SeverityLevel.HIGH),
    (2.0, SeverityLevel.MEDIUM),
    (0.0, SeverityLevel.LOW),
]


@dataclass(frozen=True)
class SeverityResult:
    """
    Hasil perhitungan severity, termasuk breakdown perhitungannya --
    supaya bisa ditampilkan ke user ("kenapa severity-nya segini?")
    dan dicatat di audit trail.
    """

    level: SeverityLevel
    base_severity: str
    onset_stage: str
    multiplier: float
    raw_score: float


def compute_severity(base_severity: str, onset_stage: str) -> SeverityResult:
    """
    Hitung severity final dari base_severity Disease (statis di KG) dan
    onset_stage yang match pada deteksi saat ini (dinamis per-case).

    Args:
        base_severity: salah satu dari "low" / "medium" / "high" / "critical".
        onset_stage: salah satu dari "early" / "middle" / "late".

    Raises:
        ValueError: jika base_severity atau onset_stage tidak dikenal.
    """
    if base_severity not in BASE_SEVERITY_SCORE:
        raise ValueError(f"base_severity tidak dikenal: {base_severity!r}")
    if onset_stage not in ONSET_STAGE_MULTIPLIER:
        raise ValueError(f"onset_stage tidak dikenal: {onset_stage!r}")

    multiplier = ONSET_STAGE_MULTIPLIER[onset_stage]
    base_score = BASE_SEVERITY_SCORE[base_severity]
    raw_score = base_score * multiplier

    return SeverityResult(
        level=_score_to_level(raw_score),
        base_severity=base_severity,
        onset_stage=onset_stage,
        multiplier=multiplier,
        raw_score=raw_score,
    )


def _score_to_level(score: float) -> SeverityLevel:
    for lower_bound, level in SEVERITY_SCORE_THRESHOLDS:
        if score >= lower_bound:
            return level
    return SeverityLevel.LOW  # fallback, seharusnya tidak pernah tercapai
