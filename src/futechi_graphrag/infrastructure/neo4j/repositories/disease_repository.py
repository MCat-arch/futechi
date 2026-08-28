from pathlib import Path
from typing import Any

from futechi_graphrag.domain.value_objects.graph_context import GraphContext
from futechi_graphrag.infrastructure.neo4j.cypher_runner import CypherRunner
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
        self, visual_features: list[str], environment_conditions: list[str]
    ) -> list[GraphContext]:
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

        query = self._query_path.read_text(encoding="utf-8")
        records = self._runner.run_read_query(
            query,
            {
                "visual_features": visual_features,
                "environment_conditions": environment_conditions,
            },
        )
        return [self._to_context(record) for record in records]

    @staticmethod
    def _to_context(record: Any) -> GraphContext:
        """Convert a Neo4j record into an immutable application DTO."""
        def values(key: str) -> tuple[dict[str, Any], ...]:
            return tuple(
                item for item in (record[key] or []) if item.get("name") is not None
            )

        return GraphContext(
            disease_id=record["disease_id"],
            disease_name=record["disease_name"],
            disease_desc=record["disease_desc"],
            base_severity=record["base_severity"],
            notifiable=bool(record["notifiable"]),
            matched_visual_features=values("matched_visual_features"),
            related_symptoms=values("related_symptoms"),
            matched_environment=values("matched_environment"),
            inspection_actions=values("inspection_actions"),
            mitigation_actions=values("mitigation_actions"),
            medical_treatments=values("medical_treatments"),
        )
