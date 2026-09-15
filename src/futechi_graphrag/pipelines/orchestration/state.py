"""Shared state contracts for diagnostic and chat orchestration flows.

These structures define the minimal application state used by LangGraph. The
chat state is intentionally separate from the case store because the checkpointer
stores only conversation history while the case store owns the official case
status and confirmation record.
"""
import operator
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from futechi_graphrag.domain.value_objects.enums import CaseStatus
from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry
from futechi_graphrag.pipelines.module_c_reasoning.dto import ChatMessage, ReasoningLLMResponse, ReasoningOutput
from futechi_graphrag.pipelines.module_a_semantic_mapping.types import FrameExtractionResult

DiagnosticStatus = Literal["processing", "manual_review", "insufficient_data", "completed"]

@dataclass
class ChatState:
    """Message state for the follow-up chat graph.

    `case_status` and `confirmed_disease` are synchronized from the CaseStore at
    the start of each turn, while `messages` are persisted by the checkpointer.
    """

    case_id: str
    cage_id: str
    case_status: str = "PENDING_CONFIRMATION"
    confirmed_disease: str | None = None
    messages: Annotated[list[ChatMessage], operator.add] = field(default_factory=list)
    visual_features: list[str] = field(default_factory=list)
    environment_conditions: list[str] = field(default_factory=list)
    graph_context: GraphContext | None = None
    cage_history: list[CageHistoryEntry] = field(default_factory=list) # tidak dianggap sebagai sumber diagnosis utama


class PipelineState(TypedDict):
    """Base state used by the diagnostic graph, following the project's staged graph pattern."""
    
  # --- input intake ---
    case_id: str
    cage_id: str
    blok_id: str
    crops: list[Any]  # ImageInput: bytes | str | Path
    capture_quality: str
    raw_environment: dict[str, float | None] | None
    excluded_disease_ids: list[str]

    # --- N1 image_extraction ---
    extraction: FrameExtractionResult

    # --- N2 semantic_mapping (+ normalisasi lingkungan) ---
    visual_features: list[VisualFeatureObservation]
    environment_conditions: list[str]
    unmapped_visuals: list[str]
    unmapped_ratio: float
    requires_manual_review: bool

    # --- N4 graph_retrieval (+ retry) ---
    graph_params: dict[str, list[str]]
    graph_context: GraphContext
    retrieval_retry_count: int

    # --- N5 differential_reasoning / N6 recommendation_builder / fallback ---
    differential: ReasoningLLMResponse
    reasoning_output: ReasoningOutput

    status: DiagnosticStatus
    notes: Annotated[list[str], operator.add]


    # case_id: str
    # raw_frames: list[Any]
    # raw_environment: Any | None
    # visual_features: list[Any] | None
    # environment_conditions: list[str] | None
    # unmapped_ratio_exceeded: bool
    # graph_context: GraphContext | None
    # reasoning_output: Any | None
    # status: Literal["processing", "insufficient_data", "manual_review", "done"]
