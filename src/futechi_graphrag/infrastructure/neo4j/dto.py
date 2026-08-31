"""
DTO (Data Transfer Object) untuk hasil retrieval dari Neo4j.

Kenapa ini di infrastructure/, bukan domain/? Struktur data di sini
(disease_id, matched_visual_features, dst) mengikuti PERSIS bentuk
RETURN clause di retrieve_disease_context.cypher -- ini representasi
"raw hasil query", bukan konsep bisnis murni. Konsep bisnis murni
(RelatedCondition, DiseaseActionBundle) sudah ada di domain layer
(Tahap 2) dan akan dibentuk oleh Modul C (Tahap 7) dari GraphContext
di sini -- bukan langsung dipakai sebagai satu tipe yang sama.

Kalau nanti query Cypher-nya berubah bentuk, yang perlu disesuaikan
cukup file ini + map_record_to_candidate(), TIDAK sampai menjalar ke
domain layer.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttributedFeature:
    """
    Representasi satu VisualFeature ATAU Symptom yang match, lengkap
    dengan atribut relasi (specificity/onset_stage/mechanism) -- kunci
    multi-hop differential reasoning di Modul C.
    """

    name: str
    specificity: str | None
    onset_stage: str | None
    mechanism: str | None


@dataclass(frozen=True)
class MatchedEnvironmentCondition:
    name: str
    strength: str | None


@dataclass(frozen=True)
class RawInspectionAction:
    name: str
    instruction: str | None


@dataclass(frozen=True)
class RawMitigationAction:
    name: str
    instruction: str | None
    priority: str | None


@dataclass(frozen=True)
class RawMedicalTreatment:
    name: str
    dosage: str | None
    withdrawal_period: str | None


@dataclass(frozen=True)
class DiseaseCandidate:
    """Satu baris hasil retrieve_disease_context.cypher, sudah di-parse jadi tipe Python."""

    disease_id: str
    disease_name: str
    desc: str
    base_severity: str
    notifiable: bool
    matched_visual_features: list[AttributedFeature]
    related_symptoms: list[AttributedFeature]
    matched_environment: list[MatchedEnvironmentCondition]
    inspection_actions: list[RawInspectionAction]
    mitigation_actions: list[RawMitigationAction]
    medical_treatments: list[RawMedicalTreatment]


@dataclass(frozen=True)
class GraphContext:
    """
    Hasil lengkap satu kali retrieval -- bisa berisi beberapa DiseaseCandidate
    sekaligus (sesuai desain: 1 query ambil semua kandidat, bukan satu-satu).
    """

    candidates: list[DiseaseCandidate]

    def is_empty(self) -> bool:
        """
        True jika retrieval tidak menemukan kandidat penyakit sama sekali
        -- ini yang memicu boundary_check ke fallback di Modul B (Tahap 5).
        """
        return len(self.candidates) == 0


def _filter_valid(items: list[dict]) -> list[dict]:
    """
    Buang entri hasil OPTIONAL MATCH yang tidak menemukan pasangan
    (Cypher mengembalikan map dengan semua field None untuk kasus ini,
    bukan menghilangkan entrinya dari list).
    """
    return [item for item in items if item.get("name") is not None]


def map_record_to_candidate(record: dict) -> DiseaseCandidate:
    """
    Konversi satu baris hasil query (dict, dari Record.data()) menjadi
    DiseaseCandidate yang sudah tervalidasi tipe.
    """
    return DiseaseCandidate(
        disease_id=record["disease_id"],
        disease_name=record["disease_name"],
        desc=record["disease_desc"],
        base_severity=record["base_severity"],
        notifiable=bool(record.get("notifiable")),
        matched_visual_features=[
            AttributedFeature(**item)
            for item in _filter_valid(record.get("matched_visual_features", []))
        ],
        related_symptoms=[
            AttributedFeature(**item)
            for item in _filter_valid(record.get("related_symptoms", []))
        ],
        matched_environment=[
            MatchedEnvironmentCondition(**item)
            for item in _filter_valid(record.get("matched_environment", []))
        ],
        inspection_actions=[
            RawInspectionAction(**item)
            for item in _filter_valid(record.get("inspection_actions", []))
        ],
        mitigation_actions=[
            RawMitigationAction(**item)
            for item in _filter_valid(record.get("mitigation_actions", []))
        ],
        medical_treatments=[
            RawMedicalTreatment(**item)
            for item in _filter_valid(record.get("medical_treatments", []))
        ],
    )
