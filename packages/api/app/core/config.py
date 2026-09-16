"""
Konfigurasi API.

Sengaja HANYA memuat hal yang khas API (database, broker, storage gambar).
Konfigurasi LLM dan Neo4j TIDAK diduplikasi di sini -- keduanya milik package
pipeline (`futechi_graphrag.config.settings`) dan dibaca dari file `.env` yang
SAMA di root repo, supaya tidak ada dua sumber kebenaran.
"""

from functools import lru_cache

from futechi_graphrag.config.settings import ENV_FILE
from futechi_graphrag.config.settings import Settings as PipelineSettings
from futechi_graphrag.config.settings import get_settings as get_pipeline_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    # --- Aplikasi ---
    app_name: str = "Futechi Poultry GraphRAG-Vet API"
    debug: bool = False

    # --- Database (PostgreSQL) ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/futechi"

    # --- Celery / Redis ---
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # --- Penyimpanan crop dari edge ---
    image_storage_dir: str = "./storage/crops"

    # --- Batasan intake ---
    # Edge mengirim 3 frame terpilih (boleh 5 untuk kasus sangat ambigu).
    max_frames_per_case: int = 5

    # --- Policy (nilai awal, perlu kalibrasi bersama pakar vet) ---
    cooldown_cycles: int = 3
    safety_net_anomaly_count: int = 3
    case_ttl_hours: int = 24

    # Riwayat kandang yang diberikan ke chat (informasional).
    cage_history_limit: int = 5
    cage_history_days: int = 90


@lru_cache
def get_settings() -> ApiSettings:
    return ApiSettings()


def get_pipeline_config() -> PipelineSettings:
    """Konfigurasi LLM & Neo4j milik pipeline (satu instance per proses)."""
    return get_pipeline_settings()
