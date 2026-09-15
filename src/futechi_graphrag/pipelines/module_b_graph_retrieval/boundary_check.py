"""
Boundary check Modul B: deteksi graph context kosong + SATU kali retry.

Retry TIDAK mengulang query yang sama. Ia mencoba memetakan ulang label
mentah yang gagal dipetakan di Modul A (`unmapped_visuals`) memakai
pencocokan fuzzy terhadap kosakata + sinonim. Query ulang hanya dijalankan
jika ada fitur canonical BARU; jika tidak, langsung kembali kosong supaya
alur lanjut ke fallback template tanpa query sia-sia.
"""
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)

DEFAULT_RETRY_FUZZY_CUTOFF = 0.85


@dataclass(frozen=True)
class RetryOutcome:
    graph_context: GraphContext
    added_visual_features: list[str] = field(default_factory=list)
    executed: bool = False


def is_context_empty(context: GraphContext | None) -> bool:
    """Return whether retrieval produced no disease candidates."""
    return context is None or context.is_empty()


def retry_with_synonym_remap(
    params: Mapping[str, Any],
    unmapped_labels: Iterable[str],
    disease_repository: DiseaseRepository,
    ontology_repository: OntologyRepository | None = None,
    fuzzy_cutoff: float = DEFAULT_RETRY_FUZZY_CUTOFF,
) -> RetryOutcome:
    """Remap unmapped raw labels once and re-query only when new canonical features appear."""
    ontology = ontology_repository or OntologyRepository()
    requested = list(params.get("visual_features", []))

    added: list[str] = []
    for label in unmapped_labels:
        canonical = ontology.resolve_visual_feature(label, fuzzy_cutoff=fuzzy_cutoff)
        if canonical and canonical not in requested and canonical not in added:
            added.append(canonical)

    if not added:
        return RetryOutcome(graph_context=GraphContext(candidates=[]))

    graph_context = disease_repository.retrieve_context(
        visual_features=requested + added,
        environment_conditions=list(params.get("environment_conditions", [])),
        excluded_disease_ids=list(params.get("excluded_disease_ids", [])),
    )
    return RetryOutcome(graph_context=graph_context, added_visual_features=added, executed=True)
