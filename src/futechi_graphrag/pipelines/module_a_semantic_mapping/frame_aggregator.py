from __future__ import annotations

from collections.abc import Sequence

from .types import AggregatedVisualCandidate, RawVisualCandidate

# ---------------------------------------------------------------------------
# Modul A: agregasi multi-frame (majority)
# ---------------------------------------------------------------------------
# Satu label dipertahankan HANYA jika muncul di lebih dari `min_frame_ratio`
# bagian frame yang dapat dinilai (default > 50% -> 2 dari 3 frame). Tanda
# yang hanya muncul di satu frame dianggap noise (blur, sudut pandang).
# Confidence akhir = rata-rata confidence pada frame tempat label muncul.
# Label yang sama muncul dua kali di satu frame dihitung sekali (ambil max).
# ---------------------------------------------------------------------------


def aggregate_candidates(
    candidates: Sequence[RawVisualCandidate],
    frames_usable: int,
    min_frame_ratio: float = 0.5,
) -> list[AggregatedVisualCandidate]:
    """Merge per-frame labels and keep those supported by a majority of usable frames."""
    if not 0.0 <= min_frame_ratio < 1.0:
        raise ValueError("min_frame_ratio must be in [0.0, 1.0)")
    if frames_usable <= 0:
        return []

    per_label: dict[str, dict[str, float]] = {}
    for index, candidate in enumerate(candidates):
        frame_key = candidate.source_frame if candidate.source_frame is not None else f"#{index}"
        frames = per_label.setdefault(candidate.label, {})
        frames[frame_key] = max(frames.get(frame_key, 0.0), candidate.confidence)

    aggregated: list[AggregatedVisualCandidate] = []
    for label, frames in per_label.items():
        support = len(frames)
        if support / frames_usable <= min_frame_ratio:
            continue
        aggregated.append(
            AggregatedVisualCandidate(
                label=label,
                confidence=sum(frames.values()) / support,
                frame_support=support,
                frames_usable=frames_usable,
            )
        )
    return aggregated
