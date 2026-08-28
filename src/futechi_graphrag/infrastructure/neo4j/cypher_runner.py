from collections.abc import Mapping
from typing import Any

from neo4j import Driver, Record


class CypherRunner:
    """Execute parameterized Cypher through a supplied Neo4j driver."""

    def __init__(self, driver: Driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    def run_read_query(
        self, query: str, params: Mapping[str, Any] | None = None
    ) -> list[Record]:
        """Run a read query and materialize its records before closing the session."""
        with self._driver.session(database=self._database) as session:
            return list(session.run(query, dict(params or {})))

    def run_write_query(
        self, query: str, params: Mapping[str, Any] | None = None
    ) -> None:
        """Run a write query and wait for its summary before closing the session."""
        with self._driver.session(database=self._database) as session:
            session.run(query, dict(params or {})).consume()
