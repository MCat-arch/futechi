"""
Cage: entitas yang merepresentasikan satu kandang/slot (1 cage = 1 ekor
ayam, sesuai keputusan desain). Menyimpan status exclusion/cooldown untuk
mengontrol apakah cage ini boleh menghasilkan ALERT baru atau tidak.

Catatan penting soal should_skip_detection(): deteksi CV di edge device
TETAP boleh berjalan di background selama cage dikecualikan -- yang
dikendalikan lewat method ini adalah apakah anomali baru boleh memicu
ALERT baru ke user, bukan apakah proses deteksinya sendiri berjalan.
"""
from __future__ import annotations

from dataclasses import dataclass

from poultry_graphrag.domain.value_objects.enums import CageStatus, CooldownReason


@dataclass
class Cage:
    cage_id: str
    zone_id: str
    status: CageStatus = CageStatus.ELIGIBLE
    cooldown_reason: CooldownReason | None = None
    cooldown_cycles_remaining: int = 0
    anomaly_count_during_cooldown: int = 0
    active_case_id: str | None = None

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------
    def should_skip_detection(self) -> bool:
        """True jika cage ini sedang dikecualikan dari ALERT baru."""
        return self.status in (CageStatus.EXCLUDED_SICK, CageStatus.COOLDOWN)

    def has_active_pending_case(self) -> bool:
        return self.active_case_id is not None

    def needs_safety_net_escalation(self, threshold: int = 3) -> bool:
        """
        True jika selama masa cooldown sudah terjadi anomali berulang
        sebanyak `threshold` kali atau lebih -- ini memicu eskalasi paksa
        ke petugas meski cage secara teknis masih cooldown, supaya
        penyakit baru yang muncul segera setelah false-alarm tidak
        terlewat begitu saja.
        """
        return (
            self.status == CageStatus.COOLDOWN
            and self.anomaly_count_during_cooldown >= threshold
        )

    # ------------------------------------------------------------------
    # Mutation methods
    # ------------------------------------------------------------------
    def start_new_case(self, case_id: str) -> None:
        self.active_case_id = case_id

    def exclude_for_sickness(self, case_id: str) -> None:
        """Dipanggil saat user konfirmasi 'Sakit'."""
        self.status = CageStatus.EXCLUDED_SICK
        self.active_case_id = case_id
        self.cooldown_reason = None
        self.cooldown_cycles_remaining = 0
        self.anomaly_count_during_cooldown = 0

    def enter_cooldown(self, reason: CooldownReason, cycles: int) -> None:
        """Dipanggil saat user konfirmasi 'Tidak Sakit' atau 'Sehat'."""
        self.status = CageStatus.COOLDOWN
        self.cooldown_reason = reason
        self.cooldown_cycles_remaining = cycles
        self.anomaly_count_during_cooldown = 0
        self.active_case_id = None

    def register_anomaly_during_cooldown(self) -> None:
        """
        Dicatat tiap kali ada anomali terdeteksi di background saat cage
        masih cooldown (dipakai untuk safety-net escalation).
        """
        self.anomaly_count_during_cooldown += 1

    def tick_cooldown_cycle(self) -> None:
        """
        Dipanggil tiap kali 1 siklus deteksi terjadwal berlalu (2x/hari).
        Otomatis membuat cage eligible lagi begitu cooldown_cycles_remaining
        mencapai 0.
        """
        if self.status != CageStatus.COOLDOWN:
            return
        self.cooldown_cycles_remaining = max(0, self.cooldown_cycles_remaining - 1)
        if self.cooldown_cycles_remaining == 0:
            self._make_eligible_again()

    def mark_recovered(self) -> None:
        """
        Dipanggil MANUAL oleh petugas setelah case CONFIRMED_SICK selesai
        masa treatment-nya. Sengaja tidak otomatis dari waktu -- masa
        penyembuhan penyakit unggas bervariasi dan tidak bisa diasumsikan.
        """
        self._make_eligible_again()

    def reset_monitoring(self) -> None:
        """
        Dipanggil MANUAL oleh petugas jika ayam di cage ini diganti/
        dipindah di tengah masa exclusion -- independen dari alur recovery
        otomatis, supaya ayam pengganti tidak ikut ter-exclude keliru.
        """
        self._make_eligible_again()

    def _make_eligible_again(self) -> None:
        self.status = CageStatus.ELIGIBLE
        self.cooldown_reason = None
        self.cooldown_cycles_remaining = 0
        self.anomaly_count_during_cooldown = 0
        self.active_case_id = None
