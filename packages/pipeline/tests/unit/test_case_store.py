import pytest

from futechi_graphrag.domain.value_objects.enums import CaseStatus
from futechi_graphrag.infrastructure.persistence.case_store import CaseStore, normalize_case_status


def test_normalize_case_status_accepts_enum_and_any_casing() -> None:
    assert normalize_case_status(CaseStatus.CONFIRMED_SICK) == "confirmed_sick"
    assert normalize_case_status("CONFIRMED_SICK") == "confirmed_sick"
    assert normalize_case_status(" Pending_Confirmation ") == "pending_confirmation"


def test_unknown_status_is_rejected() -> None:
    with pytest.raises(ValueError):
        CaseStore().upsert_case(case_id="c", cage_id="k", status="sick-ish")


def test_status_update_keeps_case_features() -> None:
    store = CaseStore()
    store.upsert_case(
        case_id="c", cage_id="k", status="pending_confirmation",
        visual_features=["conjunctivitis"], environment_conditions=["ammonia_attention"],
    )
    record = store.upsert_case(case_id="c", cage_id="k", status="CONFIRMED_SICK", confirmed_condition="CRD")

    assert record["status"] == "confirmed_sick"
    assert record["visual_features"] == ["conjunctivitis"]
    assert record["environment_conditions"] == ["ammonia_attention"]
    assert record["resolved_at"] is not None
