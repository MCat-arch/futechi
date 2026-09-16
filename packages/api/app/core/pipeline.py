"""
Jembatan API -> package pipeline.

Dependency berat (client LLM, driver Neo4j, graph terkompilasi) dibuat SEKALI
per proses lalu dipakai ulang. Membuatnya per request akan membuka koneksi
Neo4j baru terus-menerus dan mengompilasi graph berulang kali.

Kode pipeline bersifat SINKRON (driver neo4j sync, client OpenAI sync):
  - di Celery worker  -> panggil langsung (worker memang sinkron)
  - di endpoint async -> bungkus dengan run_in_threadpool, JANGAN dipanggil
    langsung di event loop
"""

from __future__ import annotations

from functools import lru_cache

from futechi_graphrag.infrastructure.llm.client import build_llm_client
from futechi_graphrag.infrastructure.neo4j.cypher_runner import CypherRunner
from futechi_graphrag.infrastructure.neo4j.driver import get_driver
from futechi_graphrag.infrastructure.neo4j.repositories.disease_repository import (
    DiseaseRepository,
)
from futechi_graphrag.infrastructure.neo4j.repositories.ontology_repository import (
    OntologyRepository,
)
from futechi_graphrag.pipelines.orchestration.diagnostic_graph import (
    DiagnosticDependencies,
    build_diagnostic_graph,
)

from app.core.config import get_pipeline_config


@lru_cache
def get_diagnostic_dependencies() -> DiagnosticDependencies:
    """Client LLM/MLLM + repository Neo4j, dibuat sekali per proses."""
    settings = get_pipeline_config()
    llm_client = build_llm_client(settings)
    ontology = OntologyRepository()
    repository = DiseaseRepository(
        CypherRunner(get_driver(), settings.neo4j_database),
        ontology_repository=ontology,
    )
    return DiagnosticDependencies(
        mllm_client=llm_client,
        llm_client=llm_client,
        disease_repository=repository,
        ontology_repository=ontology,
    )


@lru_cache
def get_diagnostic_graph():
    """Graph diagnosis terkompilasi (dipakai Celery worker)."""
    return build_diagnostic_graph(get_diagnostic_dependencies())
