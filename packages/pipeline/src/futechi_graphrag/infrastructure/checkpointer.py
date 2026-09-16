"""LangGraph checkpoint helpers used by the chat flow.

The active implementation keeps the checkpointer separate from the case store so
chat history can persist per `thread_id = case_id` without mixing it with the
official Case status data owned by the domain/application layer.
"""

from __future__ import annotations

from threading import Lock

from langgraph.checkpoint.memory import InMemorySaver

_checkpointer: InMemorySaver | None = None
_lock = Lock()


def get_checkpointer() -> InMemorySaver:
    """Return the process-wide in-memory saver used for chat persistence.

    Selalu mengembalikan instance yang SAMA -- membuat saver baru per graph
    akan menghilangkan riwayat percakapan. Untuk produksi, ganti dengan
    saver persisten (SQLite/Postgres/Redis) dengan kontrak yang sama.
    """
    global _checkpointer
    if _checkpointer is None:
        with _lock:
            if _checkpointer is None:
                _checkpointer = InMemorySaver()
    return _checkpointer
