from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar


class _HasConfidence(Protocol):
    confidence: float


C = TypeVar("C", bound=_HasConfidence)

# ---------------------------------------------------------------------------
# Modul A: confidence gate
# ---------------------------------------------------------------------------
# Fitur dengan confidence di bawah threshold DIBUANG (bukan didowngrade).
# Modul B juga memvalidasi lagi, tetapi ini filter awal agar noise tidak
# menumpuk sejak awal.
# ---------------------------------------------------------------------------


def filter_by_confidence(candidates: Sequence[C], threshold: float = 0.6) -> list[C]:
    """Keep only candidates that pass the confidence gate."""
    if not 0.0 <= threshold <= 1.0:
        raise ValueError("threshold must be between 0.0 and 1.0")

    return [candidate for candidate in candidates if candidate.confidence >= threshold]
