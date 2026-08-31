from __future__ import annotations


# ---------------------------------------------------------------------------
# Modul A: mapping validation
# ---------------------------------------------------------------------------
# Saat terlalu banyak label tidak dapat dipetakan ke canonical term, kita tidak
# ingin mengirim data berisik ke Modul B. Fungsional ini mencegah pipeline
# melanjutkan dengan data yang terlalu banyak tidak aman, dan memicu flag untuk
# manual review / insufficient data.
# ---------------------------------------------------------------------------


def validate_mapping(
    mapped_count: int,
    unmapped_count: int,
    threshold_ratio: float = 0.5,
) -> tuple[bool, float]:
    """Return whether the unmapped ratio exceeds the review threshold."""
    total = mapped_count + unmapped_count
    if total == 0:
        return False, 0.0

    unmapped_ratio = unmapped_count / total
    return unmapped_ratio > threshold_ratio, unmapped_ratio
