"""
Entry point FastAPI.

  /cases                    ingestion dari edge + daftar/detail alert
  /cases/{id}/confirm       tombol Sakit / Tidak Sakit / Sehat
  /cases/{id}/chat          chat lanjutan (via chat_graph, grounded ke KG)
  /cages                    status monitoring, Tandai Sembuh, Reset Monitoring
  /health                   liveness + kesiapan dependensi
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import cages, cases, chat
from app.core.config import get_pipeline_config, get_settings
from app.core.database import Base, engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev: buat tabel bila belum ada. Produksi sebaiknya pakai migrasi (Alembic).
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(cases.router)
app.include_router(chat.router)
app.include_router(cages.router)


@app.get("/health", tags=["health"])
async def health():
    """Liveness + ringkasan konfigurasi (tanpa kredensial)."""
    pipeline = get_pipeline_config()
    return {
        "status": "ok",
        "app": settings.app_name,
        "llm_model": pipeline.llm_model,
        "mllm_model": pipeline.mllm_model or pipeline.llm_model,
        "neo4j_uri": pipeline.neo4j_uri,
    }
