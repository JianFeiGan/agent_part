"""
Graph RAG 分类记忆服务。

Description:
    提供基于知识图谱的分类记忆查询和上下文构建能力。
    支持 Graph RAG 实体/边遍历以及 CategoryMemory 经验查询。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import CategoryMemory, GraphRAGEdge, GraphRAGEntity

logger = logging.getLogger(__name__)


@dataclass
class GraphMemoryContext:
    """Graph RAG 记忆上下文。

    封装类目相关的实体、边和类目记忆信息。

    Attributes:
        category: 商品类目。
        category_memory: 类目记忆（CategoryMemory 对象或 None）。
        entities: 实体列表。
        edges: 边列表。
    """

    category: str
    category_memory: "CategoryMemory | None" = None
    entities: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)


class GraphMemoryService:
    """Graph RAG 分类记忆服务。

    提供类目级别的实体查询、边遍历和记忆检索能力。

    Example:
        >>> service = GraphMemoryService()
        >>> context = await service.build_category_context(
        ...     session, category="digital", limit=20
        ... )
        >>> formatted = service.format_context(context)
        >>> print(formatted)
    """

    async def get_category_memory(
        self,
        session: AsyncSession,
        category: str,
    ) -> CategoryMemory | None:
        """查询指定类目的记忆记录。

        由于 category 字段是 unique 的，每个类目只有一条记忆记录。

        Args:
            session: 数据库会话。
            category: 商品类目。

        Returns:
            类目记忆记录，如果不存在则返回 None。
        """
        stmt = select(CategoryMemory).where(CategoryMemory.category == category)

        result = await session.execute(stmt)
        memory = result.scalars().first()

        logger.debug(
            f"Retrieved category memory for '{category}': {'found' if memory else 'not found'}"
        )

        return memory

    async def list_entities(
        self,
        session: AsyncSession,
        category: str,
        entity_type: str | None = None,
        limit: int = 20,
    ) -> list[GraphRAGEntity]:
        """查询指定类目下的实体列表。

        Args:
            session: 数据库会话。
            category: 商品类目。
            entity_type: 实体类型过滤（可选）。
            limit: 最大返回数量。

        Returns:
            实体列表。
        """
        stmt = (
            select(GraphRAGEntity)
            .where(GraphRAGEntity.category == category)
        )

        if entity_type:
            stmt = stmt.where(GraphRAGEntity.entity_type == entity_type)

        stmt = stmt.order_by(GraphRAGEntity.updated_at.desc()).limit(limit)

        result = await session.execute(stmt)
        entities = result.scalars().all()

        logger.debug(
            f"Retrieved {len(entities)} entities for category='{category}'"
            + (f", entity_type='{entity_type}'" if entity_type else "")
        )

        return list(entities)

    async def list_edges(
        self,
        session: AsyncSession,
        category: str,
        relationship_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询指定类目下的边关系。

        优先通过 edge 自身的 category 字段过滤；同时 JOIN 实体表获取实体名称。

        Args:
            session: 数据库会话。
            category: 商品类目。
            relationship_type: 关系类型过滤（可选）。
            limit: 最大返回数量。

        Returns:
            边关系字典列表，包含源/目标实体名称。
        """
        stmt = (
            select(
                GraphRAGEdge,
                GraphRAGEntity.name.label("source_name"),
                GraphRAGEntity.entity_type.label("source_type"),
            )
            .join(
                GraphRAGEntity,
                GraphRAGEdge.source_entity_id == GraphRAGEntity.id,
            )
            .where(GraphRAGEdge.category == category)
        )

        if relationship_type:
            stmt = stmt.where(GraphRAGEdge.relationship_type == relationship_type)

        stmt = stmt.order_by(GraphRAGEdge.weight.desc()).limit(limit)

        result = await session.execute(stmt)
        rows = result.all()

        edges = []
        for row in rows:
            edge = row[0]  # GraphRAGEdge
            edges.append({
                "id": edge.id,
                "source_entity_id": edge.source_entity_id,
                "target_entity_id": edge.target_entity_id,
                "relationship_type": edge.relationship_type,
                "weight": edge.weight,
                "evidence": edge.evidence,
                "source_name": row.source_name,
                "source_type": row.source_type,
            })

        logger.debug(
            f"Retrieved {len(edges)} edges for category='{category}'"
            + (f", relationship_type='{relationship_type}'" if relationship_type else "")
        )

        return edges

    async def build_category_context(
        self,
        session: AsyncSession,
        category: str,
        limit: int = 20,
    ) -> GraphMemoryContext:
        """构建类目上下文。

        综合查询实体、边和类目记忆，构建完整的类目知识上下文。

        Args:
            session: 数据库会话。
            category: 商品类目。
            limit: 实体返回数量限制。

        Returns:
            GraphMemoryContext 包含实体、边和类目记忆信息。
        """
        entities = await self.list_entities(session, category, limit=limit)
        edges = await self.list_edges(session, category, limit=min(limit * 2, 50))
        category_memory = await self.get_category_memory(session, category)

        entity_dicts = [
            {
                "id": e.id,
                "name": e.name,
                "entity_type": e.entity_type,
                "description": e.description,
                "aliases": e.aliases,
            }
            for e in entities
        ]

        context = GraphMemoryContext(
            category=category,
            category_memory=category_memory,
            entities=entity_dicts,
            edges=edges,
        )

        logger.info(
            f"Built category context for '{category}': "
            f"entities={len(entity_dicts)}, edges={len(edges)}, "
            f"category_memory={'present' if category_memory else 'absent'}"
        )

        return context

    def format_context(self, context: GraphMemoryContext) -> str:
        """格式化上下文为可读文本。

        输出包含：
        - 【类目记忆：category】
        - 摘要
        - 最佳实践
        - 避坑
        - 风格指南
        - 【相关实体】
        - 【关系线索】

        Args:
            context: GraphMemoryContext 实例。

        Returns:
            格式化后的文本。
        """
        parts: list[str] = []

        # 类目记忆部分
        if context.category_memory:
            cm = context.category_memory
            parts.append(f"【类目记忆：{context.category}】")
            if cm.summary:
                parts.append(f"摘要：{cm.summary}")
            if cm.best_practices:
                parts.append("最佳实践：")
                for item in cm.best_practices:
                    parts.append(f"  - {item}")
            if cm.negative_patterns:
                parts.append("避坑：")
                for item in cm.negative_patterns:
                    parts.append(f"  - {item}")
            if cm.style_guidelines:
                parts.append("风格指南：")
                for key, value in cm.style_guidelines.items():
                    parts.append(f"  - {key}: {value}")
            if cm.performance_hints:
                parts.append("性能提示：")
                for key, value in cm.performance_hints.items():
                    parts.append(f"  - {key}: {value}")
            parts.append("")

        # 相关实体部分
        if context.entities:
            parts.append("【相关实体】")
            for i, entity in enumerate(context.entities, 1):
                parts.append(
                    f"{i}. **{entity['name']}** "
                    f"({entity['entity_type']})"
                )
                if entity.get("description"):
                    parts.append(f"   {entity['description']}")
                if entity.get("aliases"):
                    parts.append(f"   别名: {', '.join(entity['aliases'])}")
            parts.append("")

        # 关系线索部分
        if context.edges:
            parts.append("【关系线索】")
            for i, edge in enumerate(context.edges, 1):
                source = edge.get("source_name", f"Entity#{edge['source_entity_id']}")
                parts.append(
                    f"{i}. {source} --[{edge['relationship_type']}]--> "
                    f"Entity#{edge['target_entity_id']} "
                    f"(权重: {edge['weight']:.2f})"
                )
                if edge.get("evidence"):
                    parts.append(f"   依据: {edge['evidence']}")
            parts.append("")

        return "\n".join(parts)
