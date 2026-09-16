"""Unit test untuk domain/entities/cage.py"""
from futechi_graphrag.domain.entities.cage import Cage
from futechi_graphrag.domain.value_objects.enums import CageStatus, CooldownReason


def _new_cage() -> Cage:
    return Cage(cage_id="B40", blok_id="Z3")


# ----------------------------------------------------------------------
# Default state
# ----------------------------------------------------------------------
def test_new_cage_is_eligible_by_default():
    cage = _new_cage()
    assert cage.status == CageStatus.ELIGIBLE
    assert cage.should_skip_detection() is False
    assert cage.has_active_pending_case() is False


# ----------------------------------------------------------------------
# exclude_for_sickness (tombol "Sakit")
# ----------------------------------------------------------------------
def test_exclude_for_sickness_sets_correct_status_and_case_id():
    cage = _new_cage()
    cage.exclude_for_sickness(case_id="CASE-001")

    assert cage.status == CageStatus.EXCLUDED_SICK
    assert cage.active_case_id == "CASE-001"
    assert cage.should_skip_detection() is True
    assert cage.has_active_pending_case() is True


# ----------------------------------------------------------------------
# enter_cooldown & tick_cooldown_cycle (tombol "Tidak Sakit"/"Sehat")
# ----------------------------------------------------------------------
def test_enter_cooldown_sets_reason_and_cycles():
    cage = _new_cage()
    cage.enter_cooldown(reason=CooldownReason.FALSE_ALARM, cycles=3)

    assert cage.status == CageStatus.COOLDOWN
    assert cage.cooldown_reason == CooldownReason.FALSE_ALARM
    assert cage.cooldown_cycles_remaining == 3
    assert cage.should_skip_detection() is True
    # active_case_id harus dikosongkan -- case-nya sudah resolved
    assert cage.active_case_id is None


def test_tick_cooldown_cycle_decrements_and_becomes_eligible_at_zero():
    cage = _new_cage()
    cage.enter_cooldown(reason=CooldownReason.NOT_SICK, cycles=2)

    cage.tick_cooldown_cycle()
    assert cage.status == CageStatus.COOLDOWN
    assert cage.cooldown_cycles_remaining == 1

    cage.tick_cooldown_cycle()
    assert cage.status == CageStatus.ELIGIBLE
    assert cage.cooldown_cycles_remaining == 0
    assert cage.cooldown_reason is None


def test_tick_cooldown_cycle_no_effect_if_not_in_cooldown():
    cage = _new_cage()  # status ELIGIBLE
    cage.tick_cooldown_cycle()
    assert cage.status == CageStatus.ELIGIBLE  # tidak error, tidak berubah


# ----------------------------------------------------------------------
# Safety-net escalation
# ----------------------------------------------------------------------
def test_register_anomaly_during_cooldown_increments_counter():
    cage = _new_cage()
    cage.enter_cooldown(reason=CooldownReason.NOT_SICK, cycles=5)

    cage.register_anomaly_during_cooldown()
    cage.register_anomaly_during_cooldown()
    assert cage.anomaly_count_during_cooldown == 2


def test_safety_net_escalation_triggers_only_after_threshold_reached():
    cage = _new_cage()
    cage.enter_cooldown(reason=CooldownReason.NOT_SICK, cycles=5)

    for _ in range(2):
        cage.register_anomaly_during_cooldown()
    assert cage.needs_safety_net_escalation(threshold=3) is False

    cage.register_anomaly_during_cooldown()  # anomali ke-3
    assert cage.needs_safety_net_escalation(threshold=3) is True


def test_safety_net_escalation_false_if_not_in_cooldown():
    cage = _new_cage()  # ELIGIBLE, bukan cooldown
    cage.anomaly_count_during_cooldown = 10  # data sisa (seharusnya tidak terjadi, tapi jaga-jaga)
    assert cage.needs_safety_net_escalation(threshold=3) is False


# ----------------------------------------------------------------------
# Recovery & reset (tombol manual petugas)
# ----------------------------------------------------------------------
def test_mark_recovered_resets_cage_to_eligible():
    cage = _new_cage()
    cage.exclude_for_sickness(case_id="CASE-001")

    cage.mark_recovered()

    assert cage.status == CageStatus.ELIGIBLE
    assert cage.active_case_id is None
    assert cage.cooldown_reason is None


def test_reset_monitoring_works_independently_from_recovery_flow():
    """
    Skenario: ayam di cage yang sedang CONFIRMED_SICK diganti/dipindah
    di tengah masa exclusion -- petugas pakai reset_monitoring(),
    BUKAN mark_recovered(), karena semantiknya beda (ayam baru vs sembuh).
    Efek akhirnya sama (kembali eligible), tapi harus tetap ada 2 method
    terpisah untuk kejelasan intent di log/audit trail.
    """
    cage = _new_cage()
    cage.exclude_for_sickness(case_id="CASE-001")

    cage.reset_monitoring()

    assert cage.status == CageStatus.ELIGIBLE
    assert cage.active_case_id is None
