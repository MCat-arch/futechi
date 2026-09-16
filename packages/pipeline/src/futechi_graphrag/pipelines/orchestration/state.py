"""Shared state contracts for diagnostic and chat orchestration flows.

These structures define the application state used by LangGraph. The chat state
is intentionally separate from the case store because the checkpointer stores
only conversation history while the case store owns the official case status and
confirmation record.

Field dengan `Annotated[list, operator.add]` memakai reducer "append":
update dari node DITAMBAHKAN ke nilai lama, bukan menimpanya.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from futechi_graphrag.domain.value_objects.enums import CaseStatus
from futechi_graphrag.domain.value_objects.observation import VisualFeatureObservation
from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry
from futechi_graphrag.pipelines.module_a_semantic_mapping.types import FrameExtractionResult
from futechi_graphrag.pipelines.module_c_reasoning.dto import (
    ChatMessage,
    ReasoningLLMResponse,
    ReasoningOutput,
)

DiagnosticStatus = Literal["processing", "manual_review", "insufficient_data", "completed"]


@dataclass
class ChatState:
    """Message state for the follow-up chat graph.

    `case_status`, `confirmed_disease`, dan fitur case disinkronkan dari
    CaseStore di awal setiap giliran; `messages` dipersist oleh checkpointer
    dan di-append (bukan ditimpa) setiap giliran.
    """

    case_id: str
    cage_id: str
    case_status: str = CaseStatus.PENDING_CONFIRMATION.value
    confirmed_disease: str | None = None
    messages: Annotated[list[ChatMessage], operator.add] = field(default_factory=list)
    visual_features: list[str] = field(default_factory=list)
    environment_conditions: list[str] = field(default_factory=list)
    graph_context: GraphContext | None = None
    cage_history: list[CageHistoryEntry] = field(default_factory=list) # tidak dianggap sebagai sumber diagnosis utama


class PipelineState(TypedDict, total=False):
    """State diagnostic_graph (alur_sistem_terpadu.md §4.1)."""

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
