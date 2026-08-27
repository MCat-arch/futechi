"""
Aturan TTL (Time To Live): batas waktu sebuah Case boleh menunggu
konfirmasi user sebelum otomatis di-eskalasi (status -> UNCONFIRMED_ESCALATED)
oleh job harian.
"""
from datetime import datetime, timedelta

# Nilai awal -- WAJIB dikalibrasi ulang setelah pilot deployment.
DEFAULT_TTL_HOURS = 24


def is_expired(
    created_at: datetime, now: datetime, ttl_hours: int | None = None
) -> bool:
    """
    True jika `now` sudah melewati batas waktu TTL dihitung dari
    `created_at`.
    """
    effective_ttl = ttl_hours if ttl_hours is not None else DEFAULT_TTL_HOURS
    deadline = created_at + timedelta(hours=effective_ttl)
    return now >= deadline
