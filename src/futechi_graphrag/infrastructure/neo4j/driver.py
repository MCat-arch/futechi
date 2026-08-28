from threading import Lock

from neo4j import Driver, GraphDatabase

from futechi_graphrag.config.settings import get_settings

_driver: Driver | None = None
_lock = Lock()


def get_driver() -> Driver:
    """Return the shared Neo4j driver and reuse its connection pool."""
    global _driver
    if _driver is None:
        with _lock:
            if _driver is None:
                settings = get_settings()
                _driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_username, settings.neo4j_password),
                )
    return _driver


def close_driver() -> None:
    """Close the shared driver during application shutdown."""
    global _driver
    with _lock:
        if _driver is not None:
            _driver.close()
            _driver = None
