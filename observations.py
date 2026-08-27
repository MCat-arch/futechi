"""
Value objects pendukung yang disimpan di dalam Case entity.

Semua immutable (frozen=True) karena ini merepresentasikan fakta yang
"terjadi" pada satu titik waktu -- kalau ada data baru, buat instance baru,
jangan mutasi instance lama.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VisualFeatureObservation:
    """
    Satu fitur visual yang teramati VLM, SUDAH lolos filter confidence
    (>= threshold, default 0.6) dan SUDAH melalui canonical mapping
    (nama sudah baku sesuai ontologi, bukan istilah mentah dari VLM).
    """

    name: str  # nama canonical, mis. "lowered_head_posture"
    confidence: float  # 0.0 - 1.0, hasil agregasi multi-frame (majority vote)


@dataclass(frozen=True)
class EnvironmentSnapshot:
    """Snapshot data sensor lingkungan pada saat deteksi terjadi."""

    temperature_c: float
    humidity_percent: float
    ammonia_ppm: float
    # contoh isi: ("humidity_attention", "ammonia_attention")
    normalized_conditions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RelatedCondition:
    """
    Satu kandidat penyakit hasil reasoning Modul C (LLM), lengkap dengan
    evidence & catatan diferensial. TIDAK ADA field skor numerik di sini --
    sesuai keputusan desain, differential reasoning dilakukan LLM secara
    naratif dari atribut relasi (specificity/onset_stage/mechanism), bukan
    dihitung sebagai skor terpisah oleh sistem.
    """

    disease_name: str
    evidence: tuple[str, ...]
    differential_note: str


@dataclass(frozen=True)
class MedicalReference:
    """
    Informasi obat referensi. Akses TERBUKA untuk semua user (sesuai
    keputusan desain), TAPI withdrawal_period wajib selalu terisi dan
    disclaimer wajib selalu disertakan.
    """

    for_condition: str
    treatment_name: str
    dosage: str
    withdrawal_period: str  # wajib -- terkait kepatuhan keamanan pangan
    disclaimer: str = (
        "Informasi referensi. Gunakan dengan pengawasan pihak berwenang "
        "(dokter hewan/petugas terlatih)."
    )

    def __post_init__(self) -> None:
        if not self.withdrawal_period.strip():
            raise ValueError(
                "withdrawal_period tidak boleh kosong -- wajib untuk "
                "kepatuhan keamanan pangan"
            )
