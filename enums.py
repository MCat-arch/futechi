"""
Enum status yang dipakai di seluruh domain layer.

Semua enum berbasis string (str, Enum) supaya:
- Bisa langsung di-serialize ke JSON tanpa konversi manual.
- Nilainya gampang dibaca di database/log (bukan angka misterius).
"""
from enum import Enum


class CaseStatus(str, Enum):
    """Status siklus hidup satu Case (satu episode deteksi anomali pada satu ekor ayam)."""

    DETECTED = "detected"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED_SICK = "confirmed_sick"
    CONFIRMED_NOT_SICK = "confirmed_not_sick"
    CONFIRMED_HEALTHY = "confirmed_healthy"
    UNCONFIRMED_ESCALATED = "unconfirmed_escalated"


class CageStatus(str, Enum):
    """Status monitoring satu Cage (1 cage = 1 ekor ayam, sesuai keputusan desain)."""

    ELIGIBLE = "eligible"  # boleh dideteksi & dialert normal
    EXCLUDED_SICK = "excluded_sick"  # dikecualikan karena sedang dalam masa treatment
    COOLDOWN = "cooldown"  # dikecualikan sementara (hasil konfirmasi tidak_sakit/sehat)


class ConfirmationType(str, Enum):
    """Tiga tombol konfirmasi yang tersedia di aplikasi user."""

    SICK = "sakit"
    NOT_SICK = "tidak_sakit"
    HEALTHY = "sehat"


class DetectionSession(str, Enum):
    """Sesi deteksi terjadwal, 2x per hari."""

    MORNING = "morning"
    EVENING = "evening"


class SeverityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CooldownReason(str, Enum):
    NOT_SICK = "not_sick"
    FALSE_ALARM = "false_alarm"
