"""
Fixture integration test -- butuh Neo4j sungguhan yang sudah di-bootstrap:

    docker compose -f ops/docker/docker-compose.neo4j.yml up -d
    python scripts/bootstrap_neo4j.py --reset --yes
    pytest -m integration

Jika Neo4j tidak bisa dihubungi, seluruh test integration di-SKIP (bukan gagal).
"""
import pytest

from futechi_graphrag.infrastructure.neo4j.cypher_runner import CypherRunner
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)


@pytest.fixture(scope="session")
def neo4j_settings():
    try:
        from futechi_graphrag.config.settings import Settings

        return Settings()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Konfigurasi Neo4j tidak tersedia: {exc}")


@pytest.fixture(scope="session")
def neo4j_driver(neo4j_settings):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        neo4j_settings.neo4j_uri,
        auth=(neo4j_settings.neo4j_username, neo4j_settings.neo4j_password),
    )
    try:
        driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001
        driver.close()
        pytest.skip(f"Neo4j tidak dapat dihubungi: {exc}")
    yield driver
    driver.close()


@pytest.fixture
def neo4j_session(neo4j_driver, neo4j_settings):
    with neo4j_driver.session(database=neo4j_settings.neo4j_database) as session:
        yield session


@pytest.fixture(scope="session")
def ontology_repository():
    return OntologyRepository()


@pytest.fixture(scope="session")
def disease_repository(neo4j_driver, neo4j_settings, ontology_repository):
    return DiseaseRepository(
        CypherRunner(neo4j_driver, neo4j_settings.neo4j_database),
        ontology_repository=ontology_repository,
    )
