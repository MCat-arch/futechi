"""Unit test untuk domain/value_objects/severity.py"""
import pytest

from futechi_graphrag.domain.value_objects.enums import SeverityLevel
from futechi_graphrag.domain.value_objects.severity import compute_severity


def test_early_stage_medium_base_gives_medium_level():
    result = compute_severity(base_severity="medium", onset_stage="early")
    assert result.multiplier == 1.0
    assert result.raw_score == 2.0
    assert result.level == SeverityLevel.MEDIUM


def test_late_stage_high_base_becomes_critical():
    result = compute_severity(base_severity="high", onset_stage="late")
    assert result.raw_score == 6.0
    assert result.level == SeverityLevel.CRITICAL


def test_early_stage_low_base_stays_low():
    result = compute_severity(base_severity="low", onset_stage="early")
    assert result.raw_score == 1.0
    assert result.level == SeverityLevel.LOW


def test_middle_stage_increases_level_compared_to_early():
    early = compute_severity(base_severity="medium", onset_stage="early")
    middle = compute_severity(base_severity="medium", onset_stage="middle")
    assert middle.raw_score > early.raw_score


def test_unknown_base_severity_raises_value_error():
    with pytest.raises(ValueError):
        compute_severity(base_severity="unknown", onset_stage="early")


def test_unknown_onset_stage_raises_value_error():
    with pytest.raises(ValueError):
        compute_severity(base_severity="low", onset_stage="unknown")


def test_severity_result_includes_breakdown_for_audit():
    result = compute_severity(base_severity="high", onset_stage="middle")
    assert result.base_severity == "high"
    assert result.onset_stage == "middle"
    # breakdown harus bisa ditelusuri ulang: base_score(high=3.0) * multiplier(middle=1.5)
    assert result.raw_score == pytest.approx(4.5)
