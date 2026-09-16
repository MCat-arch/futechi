"""Diagnostic orchestration (alur_sistem_terpadu.md §4.2).

Graph ini hanya MERANGKAI fungsi modul -- logika domain tetap dimiliki
module_a_*, module_b_*, dan module_c_reasoning.

    START
      -> image_extraction            (N1, MLLM)
      -> semantic_mapping            (N2+N3, deterministik)
         ├─ manual review ─────────────────────────────┐
         └─> graph_retrieval         (N4)              │
               ├─ ada kandidat ─> differential_reasoning (N5, LLM)
               │                    -> recommendation_builder (N6) -> END
               ├─ kosong & ada label unmapped & retry < 1
               │     -> retry_retrieval -> (routing yang sama)
               └─ kosong ─────────────────────────────> fallback -> END

Persist ke CaseStore / Case entity (N7) BELUM di graph ini -- dilakukan
use case layer setelah graph selesai.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from futechi_graphrag.domain.value_objects.observation import EnvironmentSnapshot
from futechi_graphrag.infrastructure.llm.client import LLMClient, MultimodalLLMClient
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.mllm_extractor import (
    DEFAULT_OBSERVATION_TARGETS,
    extract_frame_features,
)
from futechi_graphrag.pipelines.module_a_semantic_mapping.pipeline import (
    map_extraction_result,
)
from futechi_graphrag.pipelines.module_b_graph_retrieval import (
    build_params,
    is_context_empty,
    retrieve,
    retry_with_synonym_remap,
)
from futechi_graphrag.pipelines.module_c_reasoning.dto import CaseContextInput
from futechi_graphrag.pipelines.module_c_reasoning.fallback_template import (
    build_insufficient_data_response,
)
from futechi_graphrag.pipelines.module_c_reasoning.reasoner import (
    assemble_reasoning_output,
    generate_differential_notes,
)
from futechi_graphrag.pipelines.orchestration.state import PipelineState

if TYPE_CHECKING:
    from futechi_graphrag.config.settings import Settings

MAX_RETRIEVAL_RETRIES = 1


@dataclass(frozen=True)
class DiagnosticDependencies:
    """Semua dependency eksternal graph -- dibuat SEKALI oleh aplikasi."""

    mllm_client: MultimodalLLMClient
    llm_client: LLMClient
    disease_repository: DiseaseRepository
    ontology_repository: OntologyRepository
    observation_targets: tuple[str, ...] = DEFAULT_OBSERVATION_TARGETS
    confidence_threshold: float = 0.6
    min_frame_ratio: float = 0.5
    unmapped_threshold_ratio: float = 0.5


def build_diagnostic_dependencies(settings: Settings | None = None) -> DiagnosticDependencies:
    """Dependency produksi: client LLM dari .env (dipakai untuk MLLM & LLM) + Neo4j."""
    from futechi_graphrag.config.settings import get_settings
    from futechi_graphrag.infrastructure.llm.client import build_llm_client
    from futechi_graphrag.infrastructure.neo4j.cypher_runner import CypherRunner
    from futechi_graphrag.infrastructure.neo4j.driver import get_driver

    settings = settings or get_settings()
    llm_client = build_llm_client(settings)
    ontology = OntologyRepository()
    repository = DiseaseRepository(
        CypherRunner(get_driver(), settings.neo4j_database), ontology_repository=ontology
    )
    return DiagnosticDependencies(
        mllm_client=llm_client,
        llm_client=llm_client,
        disease_repository=repository,
        ontology_repository=ontology,
    )


def initial_diagnostic_state(
    *,
    case_id: str,
    cage_id: str,
    blok_id: str,
    crops: Sequence[Any],
    capture_quality: str = "high",
    raw_environment: Mapping[str, float | None] | None = None,
    excluded_disease_ids: Sequence[str] = (),
) -> PipelineState:
    """State awal dari payload intake (alur_sistem_terpadu.md §3.4)."""
    return {
        "case_id": case_id,
        "cage_id": cage_id,
        "blok_id": blok_id,
        "crops": list(crops),
        "capture_quality": capture_quality,
        "raw_environment": dict(raw_environment) if raw_environment else None,
        "excluded_disease_ids": list(excluded_disease_ids),
        "retrieval_retry_count": 0,
        "status": "processing",
        "notes": [],
    }


def environment_snapshot_from(
    raw_environment: Mapping[str, float | None] | None,
    conditions: Sequence[str],
) -> EnvironmentSnapshot | None:
    """Snapshot hanya dibuat jika ketiga nilai sensor tersedia (lihat K10)."""
    if not raw_environment:
        return None
    values = (
        raw_environment.get("temperature_c"),
        raw_environment.get("humidity_percent"),
        raw_environment.get("ammonia_ppm"),
    )
    if any(value is None for value in values):
        return None
    temperature, humidity, ammonia = (float(value) for value in values)
    return EnvironmentSnapshot(temperature, humidity, ammonia, tuple(conditions))


def route_after_mapping(state: PipelineState) -> Literal["graph_retrieval", "fallback"]:
    return "fallback" if state.get("requires_manual_review") else "graph_retrieval"


def route_after_retrieval(
    state: PipelineState,
) -> Literal["differential_reasoning", "retry_retrieval", "fallback"]:
    if not is_context_empty(state.get("graph_context")):
        return "differential_reasoning"
    if (
        state.get("retrieval_retry_count", 0) < MAX_RETRIEVAL_RETRIES
        and state.get("unmapped_visuals")
    ):
        return "retry_retrieval"
    return "fallback"


def build_diagnostic_graph(deps: DiagnosticDependencies):
    """Compile diagnostic graph. Panggil SEKALI lalu pakai ulang hasilnya."""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is expected in project env
        raise RuntimeError(
            "langgraph is required to build the diagnostic graph orchestration."
        ) from exc

    def image_extraction(state: PipelineState) -> dict[str, Any]:
        vocabulary = deps.ontology_repository.visual_feature_catalog(deps.observation_targets)
        extraction = extract_frame_features(
            state["crops"],
            deps.mllm_client,
            vocabulary,
            state.get("capture_quality", "high"),
        )
        return {"extraction": extraction}

    def semantic_mapping(state: PipelineState) -> dict[str, Any]:
        output = map_extraction_result(
            state["extraction"],
            state.get("raw_environment"),
            ontology_repository=deps.ontology_repository,
            observation_targets=deps.observation_targets,
            confidence_threshold=deps.confidence_threshold,
            min_frame_ratio=deps.min_frame_ratio,
            unmapped_threshold_ratio=deps.unmapped_threshold_ratio,
        )
        return {
            "visual_features": output.visual_features,
            "environment_conditions": output.environment_conditions,
            "unmapped_visuals": output.unmapped_visuals,
            "unmapped_ratio": output.unmapped_ratio,
            "requires_manual_review": output.manual_review_required,
            "notes": output.notes,
        }

    def graph_retrieval(state: PipelineState) -> dict[str, Any]:
        params = build_params(
            state.get("visual_features", []),
            state.get("environment_conditions", []),
            ontology_repository=deps.ontology_repository,
            confidence_threshold=deps.confidence_threshold,
            excluded_disease_ids=state.get("excluded_disease_ids", []),
        )
        return {"graph_params": params, "graph_context": retrieve(params, deps.disease_repository)}

    def retry_retrieval(state: PipelineState) -> dict[str, Any]:
        params = state["graph_params"]
        outcome = retry_with_synonym_remap(
            params,
            state.get("unmapped_visuals", []),
            deps.disease_repository,
            ontology_repository=deps.ontology_repository,
        )
        update: dict[str, Any] = {
            "graph_context": outcome.graph_context,
            "retrieval_retry_count": state.get("retrieval_retry_count", 0) + 1,
        }
        if outcome.executed:
            update["graph_params"] = {
                **params,
                "visual_features": [*params["visual_features"], *outcome.added_visual_features],
            }
            update["notes"] = [
                "Retry retrieval dengan fitur hasil remap label unmapped: "
                + ", ".join(outcome.added_visual_features)
            ]
        else:
            update["notes"] = ["Retry retrieval dilewati: label unmapped tidak dapat dipetakan ulang."]
        return update

    def differential_reasoning(state: PipelineState) -> dict[str, Any]:
        case_context = CaseContextInput(
            cage_id=state["cage_id"],
            blok_id=state["blok_id"],
            visual_features=state.get("visual_features", []),
            environment_snapshot=environment_snapshot_from(
                state.get("raw_environment"), state.get("environment_conditions", [])
            ),
            capture_quality=state.get("capture_quality", "high"),
        )
        return {
            "differential": generate_differential_notes(
                case_context, state["graph_context"], deps.llm_client
            )
        }

    def recommendation_builder(state: PipelineState) -> dict[str, Any]:
        return {
            "reasoning_output": assemble_reasoning_output(
                state["graph_context"], state.get("differential")
            ),
            "status": "completed",
        }

    def fallback(state: PipelineState) -> dict[str, Any]:
        return {
            "reasoning_output": build_insufficient_data_response(),
            "status": "manual_review" if state.get("requires_manual_review") else "insufficient_data",
        }

    graph = StateGraph(PipelineState)
    graph.add_node("image_extraction", image_extraction)
    graph.add_node("semantic_mapping", semantic_mapping)
    graph.add_node("graph_retrieval", graph_retrieval)
    graph.add_node("retry_retrieval", retry_retrieval)
    graph.add_node("differential_reasoning", differential_reasoning)
    graph.add_node("recommendation_builder", recommendation_builder)
    graph.add_node("fallback", fallback)

    graph.add_edge(START, "image_extraction")
    graph.add_edge("image_extraction", "semantic_mapping")
    graph.add_conditional_edges("semantic_mapping", route_after_mapping)
    graph.add_conditional_edges("graph_retrieval", route_after_retrieval)
    graph.add_conditional_edges("retry_retrieval", route_after_retrieval)
    graph.add_edge("differential_reasoning", "recommendation_builder")
    graph.add_edge("recommendation_builder", END)
    graph.add_edge("fallback", END)
    return graph.compile()
