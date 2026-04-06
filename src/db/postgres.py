"""
PostgreSQL 数据库连接管理。

Description:
    提供 PostgreSQL 连接池管理和数据库初始化功能。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""

    pass


class DatabaseManager:
    """数据库连接管理器。

    管理数据库连接池和会话生命周期。

    Example:
        >>> db_manager = DatabaseManager()
        >>> await db_manager.init()
        >>> async with db_manager.get_session() as session:
        ...     # 使用 session
        ...     pass
        >>> await db_manager.close()
    """

    def __init__(self) -> None:
        """初始化数据库管理器。"""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._initialized = False

    async def init(self) -> None:
        """初始化数据库连接池。"""
        if self._initialized:
            return

        settings = get_settings()
        self._engine = create_async_engine(
            settings.postgres_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )

        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        self._initialized = True
        logger.info(f"Database connection pool initialized: {settings.postgres_host}")

    async def close(self) -> None:
        """关闭数据库连接池。"""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话。

        Yields:
            异步数据库会话。

        Raises:
            RuntimeError: 数据库未初始化。
        """
        if not self._initialized or not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def get_engine(self) -> AsyncEngine:
        """获取数据库引擎。

        Returns:
            异步数据库引擎。

        Raises:
            RuntimeError: 数据库未初始化。
        """
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._engine


# 全局数据库管理器实例
_db_manager: DatabaseManager | None = None


async def init_db() -> None:
    """初始化数据库连接池。

    创建表结构（如果不存在）。
    """
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseManager()
        await _db_manager.init()

        # 创建表
        async with _db_manager.get_engine().begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database tables created (if not exist)")


async def close_db() -> None:
    """关闭数据库连接池。"""
    global _db_manager

    if _db_manager:
        await _db_manager.close()
        _db_manager = None


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话上下文管理器。

    Yields:
        异步数据库会话。

    Example:
        >>> async with get_db() as session:
        ...     result = await session.execute(select(KnowledgeDoc))
        ...     docs = result.scalars().all()
    """
    if _db_manager is None:
        await init_db()

    async with _db_manager.get_session() as session:  # type: ignore
        yield session
