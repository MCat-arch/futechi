from __future__ import annotations

from .types import RawVisualCandidate


# ---------------------------------------------------------------------------
# Modul A: confidence gate
# ---------------------------------------------------------------------------
# Kriteria ini penting agar label sangat lemah tidak ikut masuk ke pipeline.
# Di tahap berikutnya, Modul B juga akan melakukan validasi lagi, tetapi ini
# adalah filter awal untuk menjaga noise tidak menumpuk sejak awal.
# ---------------------------------------------------------------------------


def filter_by_confidence(
    candidates: list[RawVisualCandidate],
    threshold: float = 0.6,
) -> list[RawVisualCandidate]:
    """Keep only candidates that pass the confidence gate."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")

    return [
        candidate
        for candidate in candidates
        if candidate.confidence >= threshold
    ]
