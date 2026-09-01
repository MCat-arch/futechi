"""Shared state contracts for diagnostic and chat orchestration flows.

These structures define the minimal application state used by LangGraph. The
chat state is intentionally separate from the case store because the checkpointer
stores only conversation history while the case store owns the official case
status and confirmation record.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from futechi_graphrag.infrastructure.neo4j.dto import GraphContext
from futechi_graphrag.infrastructure.persistence.case_store import CageHistoryEntry
from futechi_graphrag.pipelines.module_c_reasoning.dto import ChatMessage


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
    messages: list[ChatMessage] = field(default_factory=list) # tidak ikut disinkronkan dari CaseStore; tetap dari checkpointer
    graph_context: GraphContext | None = None
    cage_history: list[CageHistoryEntry] = field(default_factory=list) # tidak dianggap sebagai sumber diagnosis utama


class PipelineState(TypedDict):
    """Base state used by the diagnostic graph, following the project's staged graph pattern."""

    case_id: str
    raw_frames: list[Any]
    raw_environment: Any | None
    visual_features: list[Any] | None
    environment_conditions: list[str] | None
    unmapped_ratio_exceeded: bool
    graph_context: GraphContext | None
    reasoning_output: Any | None
    status: Literal["processing", "insufficient_data", "manual_review", "done"]
