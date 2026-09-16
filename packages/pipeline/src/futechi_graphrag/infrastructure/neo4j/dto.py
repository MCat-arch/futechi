"""
DTO (Data Transfer Object) untuk hasil retrieval dari Neo4j.

Ini SATU-SATUNYA representasi GraphContext di sistem (Modul B menghasilkan,
Modul C, state LangGraph, dan chat graph mengonsumsi). Strukturnya mengikuti
RETURN clause di retrieve_disease_context.cypher -- representasi "hasil
query", bukan konsep bisnis murni. Konsep bisnis (RelatedCondition,
DiseaseActionBundle) dibentuk Modul C dari GraphContext ini.

Kalau query Cypher berubah bentuk, yang perlu disesuaikan cukup file ini +
map_record_to_candidate(), TIDAK sampai menjalar ke domain layer.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AttributedFeature:
    """
    Satu VisualFeature ATAU Symptom beserta atribut relasinya
    (specificity/onset_stage/mechanism/clinical_note) -- bahan multi-hop
    differential reasoning di Modul C.
    """

    name: str
    specificity: str | None
    onset_stage: str | None
    mechanism: str | None
    clinical_note: str | None = None


@dataclass(frozen=True)
class MatchedEnvironmentCondition:
    name: str
    strength: str | None
    note: str | None = None


@dataclass(frozen=True)
class RawInspectionAction:
    name: str
    instruction: str | None
    performed_by: str | None = None


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
    condition_type: str | None = None
    validation_note: str | None = None
    diagnostic_note: str | None = None


@dataclass(frozen=True)
class GraphContext:
    """
    Hasil lengkap satu kali retrieval -- bisa berisi beberapa DiseaseCandidate
    sekaligus (1 query ambil semua kandidat, bukan satu-satu).
    """

    candidates: list[DiseaseCandidate]

    def is_empty(self) -> bool:
        """True jika retrieval tidak menemukan kandidat -- memicu retry/fallback."""
        return len(self.candidates) == 0


def _filter_valid(items: list[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    """
    Buang entri hasil OPTIONAL MATCH yang tidak menemukan pasangan
    (Cypher mengembalikan map dengan semua field None, bukan menghilangkan
    entrinya dari list).
    """
    return [item for item in items or [] if item and item.get("name") is not None]


def _attributed(item: Mapping[str, Any]) -> AttributedFeature:
    return AttributedFeature(
        name=item["name"],
        specificity=item.get("specificity"),
        onset_stage=item.get("onset_stage"),
        mechanism=item.get("mechanism"),
        clinical_note=item.get("clinical_note"),
    )


def map_record_to_candidate(record: Mapping[str, Any]) -> DiseaseCandidate:
    """Konversi satu baris hasil query (dict dari Record.data()) menjadi DiseaseCandidate."""
    return DiseaseCandidate(
        disease_id=record["disease_id"],
        disease_name=record["disease_name"],
        desc=record.get("disease_desc") or "",
        base_severity=record["base_severity"],
        notifiable=bool(record.get("notifiable")),
        condition_type=record.get("condition_type"),
        validation_note=record.get("validation_note"),
        diagnostic_note=record.get("diagnostic_note"),
        matched_visual_features=[
            _attributed(item) for item in _filter_valid(record.get("matched_visual_features"))
        ],
        related_symptoms=[
            _attributed(item) for item in _filter_valid(record.get("related_symptoms"))
        ],
        matched_environment=[
            MatchedEnvironmentCondition(
                name=item["name"], strength=item.get("strength"), note=item.get("note")
            )
            for item in _filter_valid(record.get("matched_environment"))
        ],
        inspection_actions=[
            RawInspectionAction(
                name=item["name"],
                instruction=item.get("instruction"),
                performed_by=item.get("performed_by"),
            )
            for item in _filter_valid(record.get("inspection_actions"))
        ],
        mitigation_actions=[
            RawMitigationAction(
                name=item["name"],
                instruction=item.get("instruction"),
                priority=item.get("priority"),
            )
            for item in _filter_valid(record.get("mitigation_actions"))
        ],
        medical_treatments=[
            RawMedicalTreatment(
                name=item["name"],
                dosage=item.get("dosage"),
                withdrawal_period=item.get("withdrawal_period"),
            )
            for item in _filter_valid(record.get("medical_treatments"))
        ],
    )
