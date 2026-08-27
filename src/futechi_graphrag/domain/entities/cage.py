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
from futechi_graphrag.domain.value_objects.enums import CageStatus, CooldownReason

@dataclass
class Cage:
    cage_id: str
    blok_id: str
    status: CageStatus = CageStatus.ELIGIBLE
    cooldown_reason: CooldownReason | None = None
    cooldown_cycles_remaining: int = 0
    anomaly_count_during_cooldown: int = 0
    active_case_id: str | None = None

    #QUERY METHODS

    def should_skip_detection(self) -> bool:
        """True jika cage sedang dikecualikan dari ALert baru"""
        return self.status in (CageStatus.EXCLUDED_SICK, CageStatus.COOLDOWN)

    def has_active_pending_case(self) -> bool:
        return self.active_case_id is not None
    
    def needs_safety_net_escalation(self, threshold: int = 4) -> bool:
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

    #MUTATION METHODS

    def start_new_case(self, case_id: str) -> None:
        self.active_case_id = case_id

    def exclude_for_sickness(self, case_id: str) -> None:
        """Dipanggil saat user konfirmasi sakit """
        self.status = CageStatus.EXCLUDED_SICK
        self.active_case_id = case_id
        self.cooldown_reason = None
        self.cooldown_cycles_remaining = 0
        self.anomaly_count_during_cooldown = 0
        
