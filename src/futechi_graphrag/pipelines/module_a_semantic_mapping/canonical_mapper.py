from __future__ import annotations

from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation

from .types import RawVisualCandidate


def map_to_canonical_terms(
    candidates: list[RawVisualCandidate],
    alias_map: dict[str, list[str]],
) -> tuple[list[VisualFeatureObservation], list[str]]:
    """
    Memetakan kandidat visual mentah ke istilah kanonik menggunakan alias_map.
    Mengembalikan tuple dari:
    - daftar VisualFeatureObservation yang berhasil dipetakan
    - daftar label kandidat yang tidak dapat dipetakan
    """
    mapped: list[VisualFeatureObservation] = []
    unmapped: list[str] = []

    for candidate in candidates:
        normalized_label = candidate.label.lower().strip()
        canonical_term: str | None = None

        for canonical, aliases in alias_map.items():
            alias_values = {alias.lower().strip() for alias in aliases}
            if normalized_label in alias_values or normalized_label == canonical.lower():
                canonical_term = canonical
                break

        if canonical_term is None:
            unmapped.append(candidate.label)
            continue

        mapped.append(
            VisualFeatureObservation(
                name=canonical_term,
                confidence=candidate.confidence,
            )
        )

    return mapped, unmapped
