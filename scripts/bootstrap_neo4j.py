"""
ini adalah script untuk melakukan bootstrap neo4j dengan menjalankan file cypher yang ada di folder constraints, indexes, dan seeds.
sekali jalan seperti melakukan migrasi di database sql. script ini akan mencatat file cypher yang sudah dijalankan di node _SchemaMigration, sehingga tidak akan dijalankan lagi di bootstrap berikutnya.
"""

import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

CYPHER_ROOT = (
    ROOT / "src" / "futechi_graphrag" / "pipelines" / "knowledge_graph" / "cypher"
)

ORDERED_FOLDERS = ["constraints", "indexes", "seeds"]

def wait_for_neo4j(driver, max_retries=10, delay_seconds=5):
    for attempt in range(1, max_retries + 1):
        try:
            driver.verify_connectivity()
            print("Successfully connected to Neo4j.")
            return
        except ServiceUnavailable:
            print(f"Attempt {attempt} of {max_retries}: Neo4j is not available. Retrying in {delay_seconds} seconds...")
            time.sleep(delay_seconds)
    raise Exception("Failed to connect to Neo4j after multiple attempts.")

def get_applied_migrations(session)-> set[str]:
    """Return migration filenames already recorded in Neo4j.
    Applied migrations are stored as `_SchemaMigration` nodes. This allows
    the bootstrap process to be safely run multiple times without applying
    the same Cypher file again.
    Args:
        session: Active Neo4j session.
    Returns:
        A set containing previously applied migration filenames.
    """

    result = session.run(
        "MATCH (m:_SchemaMigration) RETURN m.filename AS filename"
    )
    return {record["filename"] for record in result}

def mark_applied(session, filename: str) -> None:
    """Record a migration as successfully applied.

    The migration filename acts as the unique identifier. MERGE makes this
    operation idempotent if the bootstrap script is executed repeatedly.

    Args:
        session: Active Neo4j session.
        filename: Migration path identifier, for example
            `constraints/001_constraints.cypher`.
    """
    session.run(
        "MERGE (m:_SchemaMigration {filename: $filename})"
        "SET m.applied_at = datetime()",
        filename=filename
    )

def split_statements(cypher_text: str) -> list[str]:
    """Split a Cypher file into executable statements.

    Empty lines and lines beginning with `//` are ignored. Statements are
    separated by semicolons. This simple parser is intended for the project's
    migration files and should not be used for complex semicolons inside
    quoted strings or procedures.

    Args:
        cypher_text: Complete contents of a Cypher migration file.

    Returns:
        A list of Cypher statements ready to execute.
    """
    statements = []
    current_statement = []
    for line in cypher_text.splitlines():
        stripped_line = line.strip()
        if stripped_line.startswith("//") or not stripped_line:
            continue
        current_statement.append(line)
        if stripped_line.endswith(";"):
            statements.append("\n".join(current_statement).rstrip(";"))
            current_statement = []
    if current_statement:
        statements.append("\n".join(current_statement))
    return statements

def run_cypher_file(session, filepath: Path) -> None:
    """Read and execute every Cypher statement in one migration file.

    Args:
        session: Active Neo4j session.
        filepath: Path to the `.cypher` migration file.

    Raises:
        OSError: If the file cannot be read.
        neo4j.exceptions.Neo4jError: If Neo4j rejects a statement.
    """
    content = filepath.read_text(encoding="utf-8")
    for statement in split_statements(content):
        session.run(statement)

def bootstrap() -> None:
    """Initialize Neo4j schema and seed data in a deterministic order.

    The process connects to Neo4j, waits until it is ready, then applies
    migrations from constraints, indexes, and seeds. Each successful file is
    recorded in `_SchemaMigration`, allowing safe reruns.

    Raises:
        RuntimeError: If Neo4j cannot become available.
        ValueError: If required Neo4j environment variables are missing.
    """
    missing = [
        name
        for name, value in {
            "NEO4J_URI": NEO4J_URI,
            "NEO4J_USERNAME": NEO4J_USERNAME,
            "NEO4J_PASSWORD": NEO4J_PASSWORD,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing required Neo4j environment variable(s): "
            + ", ".join(missing)
            + ". Define them in the project root .env file."
        )

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    wait_for_neo4j(driver)

    with driver.session() as session:
        applied = get_applied_migrations(session)

        for folder in ORDERED_FOLDERS:
            folder_path = CYPHER_ROOT / folder
            if not folder_path.exists():
                print(f"Folder {folder_path} does not exist. Skipping.")
                continue
            
            cypher_files = sorted(folder_path.glob("*.cypher"))
            for filepath in cypher_files:
                relative_name = f"{folder}/{filepath.name}"

                if relative_name in applied:
                    print(f"Skipping already applied migration: {relative_name}")
                    continue
                
                print(f"Applying migration: {relative_name}")

                try:
                    run_cypher_file(session, filepath)
                    mark_applied(session, relative_name)
                    print(f"Successfully applied migration: {relative_name}")
                except Exception as e:
                    print(f"Error occurred while applying migration {relative_name}: {e}")
                    driver.close()
                    sys.exit(1)
    driver.close()
    print("Neo4j bootstrap completed successfully.")

if __name__ == "__main__":
    bootstrap()
