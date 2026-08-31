"""
DTO khusus pipeline Modul C -- input/output reasoning yang belum tentu
sama persis dengan tipe domain (Case dkk), karena beberapa field di sini
(mis. overall_uncertainty mentah dari LLM sebelum divalidasi) masih
representasi "kerja" sebelum dilampirkan ke Case lewat
attach_reasoning_result().
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from futechi_graphrag.domain.value_objects.observation import (
    DiseaseActionBundle,
    EnvironmentSnapshot,
    InspectionAction,
    RelatedCondition,
    VisualFeatureObservation,
)
from futechi_graphrag.domain.value_objects.severity import SeverityResult


@dataclass(frozen=True)
class CaseContextInput:
    """Ringkasan case yang dikirim ke LLM sebagai konteks -- HANYA fakta
    yang sudah tervalidasi Modul A, tidak ada data mentah/belum terfilter."""

    cage_id: str
    blok_id: str
    visual_features: list[VisualFeatureObservation]
    environment_snapshot: EnvironmentSnapshot


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class ReasoningOutput:
    """
    Output lengkap Modul C untuk Tier 1 (diagnostic reasoning) -- field
    ini dirancang agar bisa langsung dioper ke
    Case.attach_reasoning_result(**dataclasses.asdict(output)) atau
    di-unpack manual di use case layer (Tahap 9).
    """

    related_conditions: list[RelatedCondition]
    recommended_checks: list[InspectionAction]
    disease_actions: dict[str, DiseaseActionBundle]
    severity: SeverityResult | None
    overall_uncertainty: str | None
    notifiable_notice: str | None


# ----------------------------------------------------------------------
# Schema structured output dari LLM -- HANYA berisi bagian generatif
# (differential_note per kandidat + catatan ketidakpastian keseluruhan).
# Field lain di ReasoningOutput dibangun deterministik dari GraphContext,
# TIDAK diminta dari LLM sama sekali -- lihat deterministic_builders.py.
# ----------------------------------------------------------------------
class DifferentialNoteItem(BaseModel):
    disease_name: str = Field(
        description="Nama penyakit, HARUS persis sama dengan salah satu "
        "nama kandidat yang diberikan di konteks -- jangan mengarang nama baru."
    )
    differential_note: str = Field(
        description="1-2 kalimat menjelaskan seberapa mungkin kandidat ini "
        "dibanding kandidat lain, berdasarkan specificity/onset_stage/"
        "mechanism yang diberikan di konteks."
    )


class ReasoningLLMResponse(BaseModel):
    differential_notes: list[DifferentialNoteItem]
    overall_uncertainty: str = Field(
        description="1 kalimat ringkas tingkat ketidakpastian case ini "
        "secara keseluruhan."
    )
