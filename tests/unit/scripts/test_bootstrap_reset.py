import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
import bootstrap_neo4j  # noqa: E402


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def run(self, statement: str, **params):
        self.statements.append(statement)
        return []


def test_reset_database_detaches_and_deletes_all_nodes() -> None:
    session = RecordingSession()
    bootstrap_neo4j.reset_database(session)
    assert session.statements == ["MATCH (n) DETACH DELETE n"]
