"""Unit test untuk domain/entities/confirmation.py"""
from datetime import datetime

import pytest

from futechi_graphrag.domain.entities.confirmation import Confirmation
from futechi_graphrag.domain.value_objects.enums import ConfirmationType

NOW = datetime(2026, 8, 27, 8, 0, 0)


def test_confirmation_sick_requires_confirmed_condition():
    with pytest.raises(ValueError):
        Confirmation(
            case_id="CASE-001",
            type=ConfirmationType.SICK,
            confirmed_by="vet-1",
            confirmed_at=NOW,
            confirmed_condition=None,  # tidak diisi -- harus gagal
        )


def test_confirmation_sick_valid_with_condition():
    confirmation = Confirmation(
        case_id="CASE-001",
        type=ConfirmationType.SICK,
        confirmed_by="vet-1",
        confirmed_at=NOW,
        confirmed_condition="Newcastle Disease",
    )
    assert confirmation.confirmed_condition == "Newcastle Disease"


def test_confirmation_healthy_does_not_require_condition():
    confirmation = Confirmation(
        case_id="CASE-001",
        type=ConfirmationType.HEALTHY,
        confirmed_by="petugas-1",
        confirmed_at=NOW,
    )
    assert confirmation.confirmed_condition is None
