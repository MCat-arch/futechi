from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    resolve_term,
)

from .types import RawVisualCandidate


def map_to_canonical_terms(
    candidates: Sequence[RawVisualCandidate],
    alias_map: Mapping[str, Sequence[str]],
    fuzzy_cutoff: float | None = None,
) -> tuple[list[RawVisualCandidate], list[RawVisualCandidate]]:
    """
    Petakan label per frame ke nama canonical (cocok persis dengan nama atau
    alias setelah normalisasi; fuzzy opsional). Dijalankan SEBELUM agregasi
    supaya sinonim berbeda di frame berbeda dihitung sebagai tanda yang sama.

    Returns:
        (kandidat terpetakan dengan label canonical, kandidat tidak terpetakan)
    """
    mapped: list[RawVisualCandidate] = []
    unmapped: list[RawVisualCandidate] = []

    for candidate in candidates:
        canonical = resolve_term(candidate.label, alias_map, fuzzy_cutoff)
        if canonical is None:
            unmapped.append(candidate)
        else:
            mapped.append(replace(candidate, label=canonical))

    return mapped, unmapped
