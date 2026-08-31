"""Minimal case persistence layer for chat-state synchronization.

The active repository does not yet connect to a production database; this store
provides the contract required by the Design Addendum: the case store owns the
official status and confirmation data, while the LangGraph checkpointer owns the
conversation history tied to `thread_id = case_id`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CageHistoryEntry:
    """A single resolved historical case for a cage, used by chat context."""

    case_id: str
    resolved_at: datetime
    outcome: str
    confirmed_condition: str | None = None


class CaseStore:
    """In-memory implementation of the case persistence contract.

    This is intentionally thin and infrastructure-agnostic; it is safe for local
    development and unit testing, while the real database-backed version can be
    swapped later without changing the chat orchestration logic.
    """

    def __init__(self) -> None:
        self._cases: dict[str, dict[str, object]] = {}

    def upsert_case(
        self,
        *,
        case_id: str,
        cage_id: str,
        status: str,
        confirmed_condition: str | None = None,
        resolved_at: datetime | None = None,
    ) -> dict[str, object]:
        if (
            resolved_at is None
            and status in {"confirmed_sick", "confirmed_not_sick", "confirmed_healthy"}
        ):
            resolved_at = datetime.utcnow()

        record = {
            "case_id": case_id,
            "cage_id": cage_id,
            "status": status,
            "confirmed_condition": confirmed_condition,
            "resolved_at": resolved_at,
        }
        self._cases[case_id] = record
        return record

    def get_case(self, case_id: str) -> dict[str, object] | None:
        return self._cases.get(case_id)

    def find_resolved_cases_by_cage(
        self,
        cage_id: str,
        exclude_case_id: str | None = None,
        limit: int = 5,
        since_days: int = 90,
    ) -> list[CageHistoryEntry]:
        """Return recent resolved cases for a cage for informational chat context."""
        if limit <= 0:
            return []

        now = datetime.utcnow()
        threshold = now - timedelta(days=since_days)
        entries: list[CageHistoryEntry] = []

        for record in self._cases.values():
            if record.get("cage_id") != cage_id:
                continue
            if exclude_case_id and record.get("case_id") == exclude_case_id:
                continue

            status = str(record.get("status") or "")
            if status not in {
                "confirmed_sick",
                "confirmed_not_sick",
                "confirmed_healthy",
            }:
                continue

            resolved_at = record.get("resolved_at")
            if not isinstance(resolved_at, datetime):
                continue
            if resolved_at < threshold:
                continue

            entries.append(
                CageHistoryEntry(
                    case_id=str(record["case_id"]),
                    resolved_at=resolved_at,
                    outcome=status,
                    confirmed_condition=(
                        str(record["confirmed_condition"])
                        if record.get("confirmed_condition") is not None
                        else None
                    ),
                )
            )

        entries.sort(key=lambda item: item.resolved_at, reverse=True)
        return entries[:limit]
