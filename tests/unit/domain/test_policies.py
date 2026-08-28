"""Unit test untuk domain/policies/*.py"""
from datetime import datetime, timedelta

from futechi_graphrag.domain.policies.cooldown_policy import (
    DEFAULT_COOLDOWN_CYCLES,
    initial_cooldown_cycles,
    is_cooldown_finished,
)
from futechi_graphrag.domain.policies.safety_net_policy import (
    DEFAULT_SAFETY_NET_THRESHOLD,
    should_force_escalate,
)
from futechi_graphrag.domain.policies.ttl_policy import DEFAULT_TTL_HOURS, is_expired


# ----------------------------------------------------------------------
# cooldown_policy
# ----------------------------------------------------------------------
def test_initial_cooldown_cycles_uses_default_when_no_override():
    assert initial_cooldown_cycles() == DEFAULT_COOLDOWN_CYCLES


def test_initial_cooldown_cycles_uses_override_when_provided():
    assert initial_cooldown_cycles(override=5) == 5


def test_is_cooldown_finished_true_at_zero_or_below():
    assert is_cooldown_finished(0) is True
    assert is_cooldown_finished(-1) is True
    assert is_cooldown_finished(1) is False


# ----------------------------------------------------------------------
# safety_net_policy
# ----------------------------------------------------------------------
def test_should_force_escalate_uses_default_threshold():
    assert should_force_escalate(DEFAULT_SAFETY_NET_THRESHOLD - 1) is False
    assert should_force_escalate(DEFAULT_SAFETY_NET_THRESHOLD) is True


def test_should_force_escalate_respects_custom_threshold():
    assert should_force_escalate(2, threshold=5) is False
    assert should_force_escalate(5, threshold=5) is True


# ----------------------------------------------------------------------
# ttl_policy
# ----------------------------------------------------------------------
def test_is_expired_uses_default_ttl_when_not_provided():
    created = datetime(2026, 8, 27, 8, 0, 0)
    just_before = created + timedelta(hours=DEFAULT_TTL_HOURS - 1)
    just_after = created + timedelta(hours=DEFAULT_TTL_HOURS + 1)

    assert is_expired(created, now=just_before) is False
    assert is_expired(created, now=just_after) is True


def test_is_expired_respects_custom_ttl_hours():
    created = datetime(2026, 8, 27, 8, 0, 0)
    assert is_expired(created, now=created + timedelta(hours=5), ttl_hours=4) is True
    assert is_expired(created, now=created + timedelta(hours=3), ttl_hours=4) is False


def test_is_expired_exactly_at_deadline_is_true():
    created = datetime(2026, 8, 27, 8, 0, 0)
    exactly_at_deadline = created + timedelta(hours=24)
    assert is_expired(created, now=exactly_at_deadline, ttl_hours=24) is True
