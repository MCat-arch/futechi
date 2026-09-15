from collections.abc import Sequence
from pathlib import Path
from typing import Any

from futechi_graphrag.infrastructure.neo4j.cypher_runner import CypherRunner
from futechi_graphrag.infrastructure.neo4j.dto import GraphContext, map_record_to_candidate
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)


class DiseaseRepository:
    """Retrieve disease context from the versioned Cypher template."""

    def __init__(
        self,
        runner: CypherRunner,
        ontology_repository: OntologyRepository | None = None,
        query_path: Path | None = None,
    ) -> None:
        self._runner = runner
        self._ontology = ontology_repository or OntologyRepository()
        self._query_path = query_path or (
            Path(__file__).parents[3]
            / "pipelines"
            / "knowledge_graph"
            / "cypher"
            / "templates"
            / "retrieve_disease_context.cypher"
        )

    def retrieve_context(
        self,
        visual_features: list[str],
        environment_conditions: list[str],
        excluded_disease_ids: Sequence[str] = (),
    ) -> GraphContext:
        """Validate canonical inputs, execute retrieval, and map every row."""
        invalid_visual = [
            name for name in visual_features
            if not self._ontology.is_valid_visual_feature(name)
        ]
        invalid_environment = [
            name for name in environment_conditions
            if not self._ontology.is_valid_environment_condition(name)
        ]
        if invalid_visual or invalid_environment:
            raise ValueError(
                "Unknown ontology terms: "
                f"visual_features={invalid_visual}, "
                f"environment_conditions={invalid_environment}"
            )
        if not visual_features:
            # Template membutuhkan minimal satu fitur visual yang cocok.
            return GraphContext(candidates=[])

        query = self._query_path.read_text(encoding="utf-8")
        records = self._runner.run_read_query(
            query,
            {
                "visual_features": visual_features,
                "environment_conditions": environment_conditions,
                "excluded_disease_ids": list(excluded_disease_ids),
            },
        )
        return GraphContext(
            candidates=[map_record_to_candidate(self._as_dict(record)) for record in records]
        )

    @staticmethod
    def _as_dict(record: Any) -> dict[str, Any]:
        """neo4j.Record -> dict; dict biasa (mis. di test) diteruskan apa adanya."""
        return record.data() if hasattr(record, "data") else dict(record)
