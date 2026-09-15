from __future__ import annotations


# ---------------------------------------------------------------------------
# Modul A: mapping validation
# ---------------------------------------------------------------------------
# Case ditandai manual review jika:
#   - tidak ada satu pun fitur canonical yang lolos (tidak ada bahan query
#     graph, padahal edge sudah mengonfirmasi anomali), ATAU
#   - proporsi label unmapped melebihi threshold (data terlalu berisik).
# ---------------------------------------------------------------------------


def validate_mapping(
    mapped_count: int,
    unmapped_count: int,
    threshold_ratio: float = 0.5,
) -> tuple[bool, float]:
    """Return (manual_review_required, unmapped_ratio)."""
    total = mapped_count + unmapped_count
    unmapped_ratio = unmapped_count / total if total else 0.0

    if mapped_count == 0:
        return True, unmapped_ratio
    return unmapped_ratio > threshold_ratio, unmapped_ratio
