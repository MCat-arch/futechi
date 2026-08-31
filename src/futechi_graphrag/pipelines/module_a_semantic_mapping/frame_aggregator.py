from __future__ import annotations

from .types import RawVisualCandidate


# ---------------------------------------------------------------------------
# Modul A: aggregation
# ---------------------------------------------------------------------------
# Bila satu fitur muncul di beberapa frame, kita ingin membuang duplikasi tapi
# tetap menjaga confidence terbaik yang muncul. Contohnya, "head down" bisa
# muncul di frame 1 dan frame 3; kita ambil score tertinggi agar hasil akhir
# lebih stabil dan tidak terlalu noisy.
# ---------------------------------------------------------------------------


def aggregate_candidates(
    candidates: list[RawVisualCandidate],
) -> list[RawVisualCandidate]:
    """Merge duplicate labels by keeping the stronger confidence score."""
    merged: dict[str, RawVisualCandidate] = {}

    for candidate in candidates:
        existing = merged.get(candidate.label)
        if existing is None or candidate.confidence > existing.confidence:
            merged[candidate.label] = candidate

    return list(merged.values())
