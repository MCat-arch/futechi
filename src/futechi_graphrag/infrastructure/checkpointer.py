"""LangGraph checkpoint helpers used by the chat flow.

The active implementation keeps the checkpointer separate from the case store so
chat history can persist per `thread_id = case_id` without mixing it with the
official Case status data owned by the domain/application layer.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver


def get_checkpointer() -> InMemorySaver:
    """Return the default in-memory saver used for local chat persistence.

    In production this may be swapped for a SQLite-backed or Redis-backed
    checkpoint saver, but the public contract remains the same: per-thread
    state is persisted independently from the case store.
    """
    return InMemorySaver()
