from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# packages/pipeline (root package ini), bukan root repo.
PACKAGE_ROOT = Path(__file__).parents[3]


def _discover_env_file() -> Path:
    """
    Cari `.env` mulai dari root package lalu naik ke atas. Di layout monorepo
    `.env` tunggal berada di root repo dan dipakai bersama oleh pipeline & API.
    """
    for directory in (PACKAGE_ROOT, *PACKAGE_ROOT.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return PACKAGE_ROOT / ".env"


ENV_FILE = _discover_env_file()
PROJECT_ROOT = ENV_FILE.parent


class Settings(BaseSettings):
    """Application settings loaded from the process environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str
    neo4j_database: str = "neo4j"

    # Endpoint Chat Completions OpenAI-compatible (OpenCode, Z.ai, vLLM, dll).
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    # Model multimodal untuk ekstraksi citra; kosong = pakai llm_model.
    mllm_model: str | None = None
    llm_temperature: float = 0.0
    # Reasoning model memakai sebagian token untuk "berpikir" -- 1500 terbukti terpotong.
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 60.0
    # Matikan jika endpoint/model tidak mendukung response_format json_object.
    llm_json_mode: bool = True


@lru_cache
def get_settings() -> Settings:
    """Return one validated settings object for the process."""
    return Settings()
