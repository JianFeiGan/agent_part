"""Alembic 迁移环境。

Description:
    异步引擎 + 项目配置驱动（src.config.settings），
    target_metadata 汇总 src/db 下全部模型。
@author ganjianfei
@version 1.0.0
2026-08-25
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from src.config.settings import get_settings
from src.db.postgres import Base

# 导入所有模型模块，确保表定义注册到 Base.metadata
from src.db import conversation_models, listing_models, models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 连接串来自项目配置（支持 ALEMBIC_DATABASE_URL / DATABASE_URL 环境变量覆盖）
settings = get_settings()
db_url = config.get_main_option("sqlalchemy.url") or settings.postgres_url
config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """以离线模式运行迁移（只生成 SQL，不连接数据库）。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """以在线模式运行迁移（asyncpg 异步引擎）。"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """以在线模式运行迁移。"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
