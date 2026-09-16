"""
Confirmation: catatan konfirmasi yang diberikan user lewat tombol
di aplikasi (Sakit / Tidak Sakit / Sehat).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from futechi_graphrag.domain.value_objects.enums import ConfirmationType


@dataclass(frozen=True)
class Confirmation:
    case_id: str
    type: ConfirmationType
    confirmed_by: str
    confirmed_at: datetime
    # Wajib diisi hanya jika type == SICK (nama kondisi yang dikonfirmasi
    # user, biasanya dipilih dari salah satu related_conditions).
    confirmed_condition: str | None = None

    def __post_init__(self) -> None:
        if self.type == ConfirmationType.SICK and not self.confirmed_condition:
            raise ValueError(
                "confirmed_condition wajib diisi ketika "
                "ConfirmationType.SICK dipilih"
            )