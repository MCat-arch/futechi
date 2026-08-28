"""Unit test untuk domain/state_machine/case_state_machine.py"""
from datetime import datetime

import pytest

from futechi_graphrag.domain.entities.case import Case
from futechi_graphrag.domain.exceptions import InvalidTransitionError
from futechi_graphrag.domain.state_machine.case_state_machine import (
    StateEvent,
    StateEventType,
    transition,
)
from futechi_graphrag.domain.value_objects.enums import (
    CaseStatus,
    ConfirmationType,
    DetectionSession,
)
from futechi_graphrag.domain.value_objects.observation import EnvironmentSnapshot

NOW = datetime(2026, 8, 27, 8, 0, 0)


def _new_case(status: CaseStatus) -> Case:
    case = Case.create_new(
        case_id="CASE-001",
        blok_id="Z3",
        cage_id="B40",
        session=DetectionSession.MORNING,
        visual_features=[],
        environment_snapshot=EnvironmentSnapshot(30.5, 76, 22),
        now=NOW,
    )
    case.status = status
    return case


# ----------------------------------------------------------------------
# USER_CONFIRMED
# ----------------------------------------------------------------------
def test_user_confirmed_valid_from_pending_confirmation():
    case = _new_case(CaseStatus.PENDING_CONFIRMATION)
    event = StateEvent(
        type=StateEventType.USER_CONFIRMED,
        now=NOW,
        confirmation_type=ConfirmationType.SICK,
        confirmed_by="vet-1",
        confirmed_condition="Newcastle Disease",
    )
    result = transition(case, event)
    assert result.status == CaseStatus.CONFIRMED_SICK
    assert result.confirmed_by == "vet-1"


def test_user_confirmed_valid_from_unconfirmed_escalated():
    """Case yang sudah ter-eskalasi TTL tetap harus bisa dikonfirmasi user."""
    case = _new_case(CaseStatus.UNCONFIRMED_ESCALATED)
    event = StateEvent(
        type=StateEventType.USER_CONFIRMED,
        now=NOW,
        confirmation_type=ConfirmationType.NOT_SICK,
        confirmed_by="petugas-2",
    )
    result = transition(case, event)
    assert result.status == CaseStatus.CONFIRMED_NOT_SICK


def test_user_confirmed_invalid_from_already_confirmed_status():
    case = _new_case(CaseStatus.CONFIRMED_SICK)
    event = StateEvent(
        type=StateEventType.USER_CONFIRMED,
        now=NOW,
        confirmation_type=ConfirmationType.HEALTHY,
        confirmed_by="vet-1",
    )
    with pytest.raises(InvalidTransitionError) as exc_info:
        transition(case, event)

    assert exc_info.value.current_status == "confirmed_sick"
    assert exc_info.value.attempted_event == "user_confirmed"


# ----------------------------------------------------------------------
# TTL_EXPIRED
# ----------------------------------------------------------------------
def test_ttl_expired_valid_from_pending_confirmation():
    case = _new_case(CaseStatus.PENDING_CONFIRMATION)
    event = StateEvent(type=StateEventType.TTL_EXPIRED, now=NOW)

    result = transition(case, event)
    assert result.status == CaseStatus.UNCONFIRMED_ESCALATED


def test_ttl_expired_invalid_from_detected_status():
    """Case yang belum sampai PENDING_CONFIRMATION (masih diproses pipeline)
    tidak seharusnya bisa di-TTL-expire."""
    case = _new_case(CaseStatus.DETECTED)
    event = StateEvent(type=StateEventType.TTL_EXPIRED, now=NOW)

    with pytest.raises(InvalidTransitionError):
        transition(case, event)


def test_ttl_expired_invalid_from_already_resolved_status():
    case = _new_case(CaseStatus.CONFIRMED_HEALTHY)
    event = StateEvent(type=StateEventType.TTL_EXPIRED, now=NOW)

    with pytest.raises(InvalidTransitionError):
        transition(case, event)


# ----------------------------------------------------------------------
# NEW_DETECTION_MERGED / REASONING_ATTACHED / INSUFFICIENT_DATA
# (hanya validasi kelayakan transisi, mutasi data dilakukan terpisah oleh use case)
# ----------------------------------------------------------------------
def test_reasoning_attached_valid_from_detected():
    case = _new_case(CaseStatus.DETECTED)
    event = StateEvent(type=StateEventType.REASONING_ATTACHED, now=NOW)
    # tidak raise -- transisi valid, meski mutasi data sesungguhnya
    # dilakukan lewat Case.attach_reasoning_result() secara terpisah
    transition(case, event)


def test_insufficient_data_invalid_from_confirmed_status():
    case = _new_case(CaseStatus.CONFIRMED_SICK)
    event = StateEvent(type=StateEventType.INSUFFICIENT_DATA, now=NOW)
    with pytest.raises(InvalidTransitionError):
        transition(case, event)


def test_new_detection_merged_valid_from_pending_confirmation():
    """Ini skenario 'deteksi sesi ke-2 sebelum user sempat konfirmasi'."""
    case = _new_case(CaseStatus.PENDING_CONFIRMATION)
    event = StateEvent(type=StateEventType.NEW_DETECTION_MERGED, now=NOW)
    transition(case, event)  # tidak raise
