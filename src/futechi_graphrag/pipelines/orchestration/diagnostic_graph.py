"""Diagnostic orchestration wrapper.

This file is intentionally lightweight: the actual domain-specific logic is still
owned by the stage-specific modules (`module_a_*`, `module_b_*`, and
`module_c_reasoning`). The orchestration layer only wires them together in a
single graph and exposes a minimal entry point for the application.
"""

from __future__ import annotations

from typing import Any

from futechi_graphrag.pipelines.orchestration.state import PipelineState


def build_diagnostic_graph():
    """Construct the diagnostic graph with the staged flow.

    The real implementation can be expanded later with module-specific nodes, but
    the contract remains: run Module A -> Module B -> Module C / fallback.
    """
    try:
        from langgraph.graph import END, StateGraph
    except ImportError as exc:  # pragma: no cover - dependency is expected in project env
        raise RuntimeError(
            "langgraph is required to build the diagnostic graph orchestration."
        ) from exc

    graph = StateGraph(PipelineState)
    graph.add_node("module_a", lambda state: state)
    graph.add_node("module_b", lambda state: state)
    graph.add_node("module_c", lambda state: state)
    graph.add_node("fallback", lambda state: state)
    graph.set_entry_point("module_a")
    graph.add_edge("module_a", "module_b")
    graph.add_edge("module_b", "module_c")
    graph.add_edge("module_c", END)
    graph.add_edge("fallback", END)
    return graph.compile()


def run_diagnostic_graph(state: dict[str, Any]) -> dict[str, Any]:
    """Convenience wrapper for invoking the graph with a Python dict state."""
    graph = build_diagnostic_graph()
    return graph.invoke(state)
