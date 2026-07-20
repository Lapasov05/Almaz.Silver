"""Async SQLAlchemy engine + session factory + FastAPI DI dependency.

TZ 4-bo'lim qatlamlari: Repository/Service qatlamlari shu sessiyaga tayanadi.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,  # uzilgan ulanishlarni avtomatik tiklash
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit'dan keyin obyektlar yaroqli qoladi
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """So'rov davomidagi DB sessiyasi (FastAPI Depends orqali beriladi)."""
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def task_session() -> AsyncGenerator[AsyncSession, None]:
    """Celery task uchun mustaqil sessiya — har task o'z event loop'ida ishlaydi.

    NullPool: ulanish task oxirida yopiladi (loop'lar aro pool muammosini oldini oladi).
    Ishlatish: `async with task_session() as db: ...` (asyncio.run ichida).
    """
    task_engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(task_engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await task_engine.dispose()
