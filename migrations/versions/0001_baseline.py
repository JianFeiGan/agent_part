"""基线迁移：创建全部表结构与 pgvector 扩展。

与 src/db 下 SQLAlchemy 模型（models / listing_models / conversation_models）
保持一致。采用 metadata.create_all 方式建表：

- 全新环境：`uv run alembic upgrade head` 一步到位
- 已通过 create_all 建过表的存量库：`uv run alembic stamp head` 补记版本，
  后续 schema 变更一律通过新增迁移脚本管理

Revision ID: 0001
Revises:
Create Date: 2026-08-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.db.postgres import Base

# 导入所有模型模块，确保表定义注册到 Base.metadata
from src.db import conversation_models, listing_models, models  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 pgvector 扩展和全部表结构。"""
    # PGVector（KnowledgeDoc/Chunk、GraphRAG 实体等 Vector 列依赖）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """删除全部表结构。

    注意：不卸载 vector 扩展（可能被其他库对象共享）。
    """
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
