"""Regresi B6 (nama field recommended_checks) & B7 (default threshold safety-net)."""
from dataclasses import asdict, fields
from datetime import datetime

from futechi_graphrag.domain.entities.cage import Cage
from futechi_graphrag.domain.entities.case import Case
from futechi_graphrag.domain.policies.safety_net_policy import DEFAULT_SAFETY_NET_THRESHOLD
from futechi_graphrag.domain.value_objects.enums import CooldownReason, DetectionSession
from futechi_graphrag.domain.value_objects.observation import EnvironmentSnapshot, InspectionAction


def test_attach_reasoning_result_fills_declared_recommended_checks_field() -> None:
    case = Case.create_new(
        case_id="C1",
        blok_id="Z3",
        cage_id="B40",
        session=DetectionSession.MORNING,
        visual_features=[],
        environment_snapshot=EnvironmentSnapshot(30.0, 70.0, 10.0),
        now=datetime(2026, 9, 15, 8, 0),
    )
    checks = [InspectionAction("observe_breathing", "Dengarkan napas")]

    case.attach_reasoning_result(related_conditions=[], recommended_checks=checks, disease_actions={}, severity=None)

    assert "recommended_checks" in {f.name for f in fields(Case)}
    assert asdict(case)["recommended_checks"] == [asdict(checks[0])]


def test_cage_safety_net_default_follows_policy_threshold() -> None:
    cage = Cage(cage_id="B40", blok_id="Z3")
    cage.enter_cooldown(CooldownReason.NOT_SICK, cycles=3)

    for _ in range(DEFAULT_SAFETY_NET_THRESHOLD - 1):
        cage.register_anomaly_during_cooldown()
    assert cage.needs_safety_net_escalation() is False

    cage.register_anomaly_during_cooldown()
    assert cage.needs_safety_net_escalation() is True
