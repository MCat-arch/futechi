"""
Case State Machine: definisi event & transisi valid untuk Case.status.

Kenapa dipisah dari Case entity?
- Definisi "transisi mana yang SAH" perlu terpusat di 1 tempat sebagai
  tabel yang mudah dibaca dan diaudit -- bukan tersebar sebagai if/else
  di berbagai use case.
- Case entity tetap sederhana: hanya menyimpan data + method mutasi
  spesifik dirinya sendiri (resolve, escalate_unconfirmed, dst),
  tanpa perlu tahu "urutan status mana yang boleh terjadi".

ATURAN PENTING: use case layer WAJIB memproses semua perubahan status
Case lewat transition() di file ini -- JANGAN panggil method
Case.resolve() / Case.escalate_unconfirmed() secara langsung dari luar,
supaya validasi transisi tidak pernah bisa dilewati.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from poultry_graphrag.domain.entities.case import Case
from poultry_graphrag.domain.exceptions import InvalidTransitionError
from poultry_graphrag.domain.value_objects.enums import CaseStatus, ConfirmationType


class StateEventType(str, Enum):
    NEW_DETECTION_MERGED = "new_detection_merged"
    REASONING_ATTACHED = "reasoning_attached"
    INSUFFICIENT_DATA = "insufficient_data"
    USER_CONFIRMED = "user_confirmed"
    TTL_EXPIRED = "ttl_expired"


@dataclass(frozen=True)
class StateEvent:
    type: StateEventType
    now: datetime
    # Hanya relevan untuk event USER_CONFIRMED:
    confirmation_type: ConfirmationType | None = None
    confirmed_by: str | None = None


# Tabel transisi valid: {status_saat_ini: {event_yang_diizinkan_dari_status_ini}}
#
# Catatan: status CONFIRMED_* sengaja TIDAK punya event lanjutan yang valid --
# case yang sudah resolved tidak boleh diproses ulang di hari yang sama.
VALID_TRANSITIONS: dict[CaseStatus, frozenset[StateEventType]] = {
    CaseStatus.DETECTED: frozenset(
        {
            StateEventType.REASONING_ATTACHED,
            StateEventType.INSUFFICIENT_DATA,
            StateEventType.NEW_DETECTION_MERGED,
        }
    ),
    CaseStatus.PENDING_CONFIRMATION: frozenset(
        {
            StateEventType.USER_CONFIRMED,
            StateEventType.TTL_EXPIRED,
            StateEventType.NEW_DETECTION_MERGED,
        }
    ),
    CaseStatus.UNCONFIRMED_ESCALATED: frozenset(
        {
            StateEventType.USER_CONFIRMED,
            StateEventType.NEW_DETECTION_MERGED,
        }
    ),
    CaseStatus.CONFIRMED_SICK: frozenset(),
    CaseStatus.CONFIRMED_NOT_SICK: frozenset(),
    CaseStatus.CONFIRMED_HEALTHY: frozenset(),
}


def transition(case: Case, event: StateEvent) -> Case:
    """
    Validasi & terapkan satu event ke Case.

    Mengubah `case` secara in-place (mutasi) dan mengembalikannya juga
    untuk kenyamanan chaining di use case layer, mis:
        case = transition(case, StateEvent(...))

    Untuk event USER_CONFIRMED dan TTL_EXPIRED, method mutasi yang sesuai
    di Case entity langsung dipanggil di sini setelah validasi lolos.

    Untuk event NEW_DETECTION_MERGED / REASONING_ATTACHED / INSUFFICIENT_DATA,
    transition() HANYA memvalidasi bahwa event tsb sah dari status saat ini
    -- mutasi datanya sendiri (yang butuh data tambahan seperti
    visual_features baru atau related_conditions) tetap dipanggil langsung
    oleh use case ke method Case yang sesuai SETELAH transition() ini
    memvalidasi kelayakannya. Ini supaya signature transition() tidak perlu
    membawa seluruh kemungkinan payload dari semua jenis event.

    Raises:
        InvalidTransitionError: jika event tidak diizinkan dari status saat ini.
    """
    allowed_events = VALID_TRANSITIONS.get(case.status, frozenset())
    if event.type not in allowed_events:
        raise InvalidTransitionError(
            current_status=case.status.value,
            attempted_event=event.type.value,
        )

    if event.type == StateEventType.USER_CONFIRMED:
        assert event.confirmation_type is not None, (
            "StateEvent USER_CONFIRMED wajib menyertakan confirmation_type"
        )
        assert event.confirmed_by is not None, (
            "StateEvent USER_CONFIRMED wajib menyertakan confirmed_by"
        )
        case.resolve(event.confirmation_type, event.confirmed_by, event.now)

    elif event.type == StateEventType.TTL_EXPIRED:
        case.escalate_unconfirmed()

    # NEW_DETECTION_MERGED / REASONING_ATTACHED / INSUFFICIENT_DATA:
    # validasi transisi sudah lolos di atas, mutasi datanya menyusul
    # dipanggil use case langsung ke Case.merge_new_detection() /
    # Case.attach_reasoning_result() / Case.mark_insufficient_data().

    return case
