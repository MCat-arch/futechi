"""
Koneksi database async (SQLAlchemy 2.0).

Ada DUA cara memperoleh session, dan keduanya diperlukan:

  get_db()       -> untuk request FastAPI. Memakai engine & pool bersama;
                    seluruh request hidup di satu event loop.

  task_session() -> untuk Celery task. Tiap task memanggil asyncio.run()
                    dengan event loop BARU, sementara koneksi asyncpg terikat
                    pada loop tempat ia dibuat. Memakai pool bersama di sana
                    membuat task kedua gagal dengan "attached to a different
                    loop", jadi task membuat engine sendiri tanpa pool
                    (NullPool) lalu membuangnya setelah selesai.
"""

from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # cek koneksi hidup sebelum dipakai (hindari stale conn)
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """Base class untuk semua ORM model."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: satu session per request, commit di akhir."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Session untuk Celery task (engine sendiri, tanpa pool lintas loop)."""
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(
        task_engine, class_=AsyncSession, expire_on_commit=False
    )
    try:
        async with session_factory() as session:
            yield session
    finally:
        await task_engine.dispose()
