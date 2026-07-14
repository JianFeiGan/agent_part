"""
分类记忆存储服务。

Description:
    提供分类记忆的存储、检索和遗忘管理能力。
    支持自动分类、向量化存储、相似度检索和基于重要性的遗忘机制。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import AgentMemory
from src.rag.embeddings import get_embedding_service
from src.rag.memory_classifier import MemoryClassifier, MemoryType

logger = logging.getLogger(__name__)


class MemoryStore:
    """分类记忆存储服务。

    提供记忆的自动分类、向量化存储、相似度检索和遗忘管理。

    Example:
        >>> store = MemoryStore()
        >>> await store.store(session, content="智能手表需要突出科技感", agent_name="CreativePlanner")
        >>> results = await store.retrieve(session, query="手表设计要点", agent_name="CreativePlanner")
    """

    def __init__(self) -> None:
        """初始化记忆存储。"""
        self.settings = get_settings()
        self._classifier = MemoryClassifier()

    async def store(
        self,
        session: AsyncSession,
        content: str,
        agent_name: str,
        *,
        memory_type: MemoryType | None = None,
        category: str | None = None,
        importance: float = 0.5,
        source_task_id: str | None = None,
        tenant_id: str | None = None,
    ) -> AgentMemory:
        """存储记忆。

        自动分类 + 向量化 + 存储到 AgentMemory 表，超限时遗忘低重要性记忆。

        Args:
            session: 数据库会话。
            content: 记忆内容。
            agent_name: 智能体名称。
            memory_type: 记忆类型（可选，自动分类时忽略）。
            category: 商品类目（可选）。
            importance: 重要性评分。
            source_task_id: 来源任务 ID（可选）。
            tenant_id: 租户 ID（可选）。

        Returns:
            存储的 AgentMemory 对象。
        """
        # 自动分类
        if memory_type is None and self.settings.memory_auto_classify:
            memory_type = await self._classifier.classify(content)
        elif memory_type is None:
            memory_type = MemoryType.SEMANTIC

        # 提取关键概念
        key_concepts = await self._classifier.extract_key_concepts(content)

        # 向量化
        embedding: list[float] | None = None
        try:
            embedding_service = get_embedding_service()
            embedding = await embedding_service.aembed_single(content)
        except Exception as e:
            logger.warning(f"记忆向量化失败: {e}")

        # 检查是否超限
        await self._check_capacity(session, agent_name, memory_type, tenant_id=tenant_id)

        # 创建记忆记录
        memory = AgentMemory(
            tenant_id=tenant_id,
            agent_name=agent_name,
            category=category,
            memory_type=memory_type.value,
            content=content,
            key_concepts=key_concepts,
            embedding=embedding,
            importance=importance,
            source_task_id=source_task_id,
        )
        session.add(memory)
        await session.flush()

        logger.info(
            f"存储记忆: agent='{agent_name}', type='{memory_type.value}', "
            f"category='{category}', importance={importance:.2f}"
        )

        return memory

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        agent_name: str,
        *,
        memory_type: MemoryType | None = None,
        category: str | None = None,
        top_k: int = 5,
        tenant_id: str | None = None,
    ) -> list[AgentMemory]:
        """检索记忆。

        向量相似度检索 + 类型过滤 + 更新访问计数。

        Args:
            session: 数据库会话。
            query: 查询文本。
            agent_name: 智能体名称。
            memory_type: 记忆类型过滤（可选）。
            category: 商品类目过滤（可选）。
            top_k: 返回数量。
            tenant_id: 租户 ID（可选）。

        Returns:
            检索到的记忆列表。
        """
        # 向量化查询
        query_embedding: list[float] | None = None
        try:
            embedding_service = get_embedding_service()
            query_embedding = await embedding_service.aembed_single(query)
        except Exception as e:
            logger.warning(f"查询向量化失败: {e}")

        # 构建查询
        tenant_condition = (
            (AgentMemory.tenant_id == tenant_id) if tenant_id else AgentMemory.tenant_id.is_(None)
        )

        stmt = (
            select(AgentMemory).where(AgentMemory.agent_name == agent_name).where(tenant_condition)
        )

        if memory_type:
            stmt = stmt.where(AgentMemory.memory_type == memory_type.value)

        if category:
            stmt = stmt.where(AgentMemory.category == category)

        # 向量相似度排序（如果有 embedding）
        if query_embedding:

            stmt = stmt.order_by(AgentMemory.embedding.cosine_distance(query_embedding))
        else:
            stmt = stmt.order_by(AgentMemory.importance.desc())

        stmt = stmt.limit(top_k)
        result = await session.execute(stmt)
        memories = result.scalars().all()

        # 更新访问计数
        for memory in memories:
            memory.access_count += 1
            memory.last_accessed_at = datetime.now(tz=None)

        await session.flush()

        logger.debug(
            f"检索记忆: agent='{agent_name}', query='{query[:30]}...', results={len(memories)}"
        )

        return list(memories)

    async def _check_capacity(
        self,
        session: AsyncSession,
        agent_name: str,
        memory_type: MemoryType,
        *,
        tenant_id: str | None = None,
    ) -> None:
        """检查记忆容量，超限时遗忘低重要性记忆。

        Args:
            session: 数据库会话。
            agent_name: 智能体名称。
            memory_type: 记忆类型。
            tenant_id: 租户 ID（可选）。
        """
        max_per_type = self.settings.memory_max_per_type

        tenant_condition = (
            (AgentMemory.tenant_id == tenant_id) if tenant_id else AgentMemory.tenant_id.is_(None)
        )

        # 统计当前数量
        count_stmt = (
            select(func.count(AgentMemory.id))
            .where(AgentMemory.agent_name == agent_name)
            .where(AgentMemory.memory_type == memory_type.value)
            .where(tenant_condition)
        )
        result = await session.execute(count_stmt)
        current_count = result.scalar() or 0

        if current_count >= max_per_type:
            # 遗忘低重要性记忆
            await self._forget_least_important(
                session,
                agent_name,
                memory_type,
                count=current_count - max_per_type + 1,
                tenant_id=tenant_id,
            )

    async def _forget_least_important(
        self,
        session: AsyncSession,
        agent_name: str,
        memory_type: MemoryType,
        count: int = 1,
        *,
        tenant_id: str | None = None,
    ) -> int:
        """遗忘最低评分的记忆。

        基于 importance + access_count 综合评分删除最低评分记忆。

        Args:
            session: 数据库会话。
            agent_name: 智能体名称。
            memory_type: 记忆类型。
            count: 需要遗忘的数量。
            tenant_id: 租户 ID（可选）。

        Returns:
            实际删除的数量。
        """
        tenant_condition = (
            (AgentMemory.tenant_id == tenant_id) if tenant_id else AgentMemory.tenant_id.is_(None)
        )

        # 查询最低评分记忆（importance 低且 access_count 低）
        stmt = (
            select(AgentMemory.id)
            .where(AgentMemory.agent_name == agent_name)
            .where(AgentMemory.memory_type == memory_type.value)
            .where(tenant_condition)
            .order_by(AgentMemory.importance.asc(), AgentMemory.access_count.asc())
            .limit(count)
        )
        result = await session.execute(stmt)
        ids_to_delete = [row[0] for row in result.all()]

        if ids_to_delete:
            delete_stmt = delete(AgentMemory).where(AgentMemory.id.in_(ids_to_delete))
            await session.execute(delete_stmt)
            await session.flush()

            logger.info(
                f"遗忘记忆: agent='{agent_name}', type='{memory_type.value}', "
                f"count={len(ids_to_delete)}"
            )

        return len(ids_to_delete)

    async def forget_expired(
        self,
        session: AsyncSession,
        *,
        tenant_id: str | None = None,
    ) -> int:
        """清理超过遗忘阈值且 access_count=0 的记忆。

        Args:
            session: 数据库会话。
            tenant_id: 租户 ID（可选）。

        Returns:
            删除的记忆数量。
        """
        threshold_days = self.settings.memory_forget_threshold_days
        cutoff_date = datetime.now(tz=None) - timedelta(days=threshold_days)

        tenant_condition = (
            (AgentMemory.tenant_id == tenant_id) if tenant_id else AgentMemory.tenant_id.is_(None)
        )

        stmt = (
            delete(AgentMemory)
            .where(AgentMemory.access_count == 0)
            .where(AgentMemory.created_at < cutoff_date)
            .where(tenant_condition)
        )
        result = await session.execute(stmt)
        await session.flush()

        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(f"清理过期记忆: count={deleted_count}, threshold={threshold_days}天")

        return deleted_count


_memory_store: MemoryStore | None = None


def get_memory_store() -> MemoryStore:
    """获取 MemoryStore 单例。

    Returns:
        MemoryStore 实例。
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store
