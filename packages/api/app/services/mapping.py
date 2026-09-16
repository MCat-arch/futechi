"""
Pemetaan objek pipeline (dataclass) <-> JSON yang disimpan di Postgres.

Semua konversi dikumpulkan di satu file supaya kalau bentuk ReasoningOutput
berubah, yang perlu disesuaikan cukup di sini -- bukan tersebar di service,
task, dan route.
"""

from __future__ import annotations

from typing import Any

from futechi_graphrag.domain.value_objects.observation import (
    DiseaseActionBundle,
    MedicalReference,
    MitigationAction,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import ReasoningOutput


def visual_features_to_json(features: list[Any]) -> list[dict]:
    return [{"name": f.name, "confidence": round(float(f.confidence), 4)} for f in features]


def severity_to_json(severity: Any | None) -> dict | None:
    if severity is None:
        return None
    return {
        "level": severity.level.value,
        "base_severity": severity.base_severity,
        "onset_stage": severity.onset_stage,
        "multiplier": severity.multiplier,
        "raw_score": severity.raw_score,
    }


def _mitigation_to_json(action: MitigationAction) -> dict:
    return {
        "name": action.name,
        "instruction": action.instruction,
        "priority": action.priority,
    }


def _medical_reference_to_json(reference: MedicalReference) -> dict:
    return {
        "for_condition": reference.for_condition,
        "treatment_name": reference.treatment_name,
        "dosage": reference.dosage,
        "withdrawal_period": reference.withdrawal_period,
        "disclaimer": reference.disclaimer,
    }


def disease_actions_to_json(bundles: dict[str, DiseaseActionBundle]) -> dict[str, dict]:
    """Disimpan untuk SEMUA kandidat, tapi baru dibuka saat konfirmasi "Sakit"."""
    return {
        name: {
            "mitigations": [_mitigation_to_json(m) for m in bundle.mitigations],
            "medical_references": [
                _medical_reference_to_json(r) for r in bundle.medical_references
            ],
        }
        for name, bundle in bundles.items()
    }


def reasoning_to_json(output: ReasoningOutput) -> dict[str, Any]:
    """Seluruh hasil Modul C dalam bentuk siap simpan."""
    return {
        "related_conditions": [
            {
                "disease_name": condition.disease_name,
                "evidence": list(condition.evidence),
                "differential_note": condition.differential_note,
            }
            for condition in output.related_conditions
        ],
        "recommended_checks": [
            {"name": check.name, "instruction": check.instruction}
            for check in output.recommended_checks
        ],
        "disease_actions": disease_actions_to_json(output.disease_actions),
        "severity_detail": severity_to_json(output.severity),
        "severity_level": output.severity.level if output.severity else None,
        "overall_uncertainty": output.overall_uncertainty,
        "notifiable_notice": output.notifiable_notice,
    }


def pipeline_state_to_json(state: dict[str, Any]) -> dict[str, Any]:
    """Bagian state diagnostic_graph yang perlu disimpan di kolom Case."""
    payload: dict[str, Any] = {
        "visual_features": visual_features_to_json(state.get("visual_features", [])),
        "environment_conditions": list(state.get("environment_conditions", [])),
        "unmapped_visuals": list(state.get("unmapped_visuals", [])),
        "requires_manual_review": bool(state.get("requires_manual_review", False)),
        "pipeline_status": state.get("status"),
        "pipeline_notes": list(state.get("notes", [])),
    }
    reasoning = state.get("reasoning_output")
    if reasoning is not None:
        payload.update(reasoning_to_json(reasoning))
    return payload
