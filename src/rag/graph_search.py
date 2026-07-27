"""
Graph RAG Global/Local Search 服务。

Description:
    提供基于知识图谱的 Local Search、Global Search 和 Hybrid Search 能力。
    Local Search: 实体推理链（关键词匹配种子实体 -> 查询关系 -> 构建子图上下文 -> LLM 推理）。
    Global Search: Map-Reduce 社区摘要（查询社区 -> 每个社区生成部分回答 -> 汇总）。
    Hybrid Search: 结合 Local + Global 结果。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.models import CommunitySummary, GraphRAGEdge, GraphRAGEntity

logger = logging.getLogger(__name__)


@dataclass
class GraphSearchResult:
    """Graph RAG 搜索结果。

    Attributes:
        answer: 生成的回答。
        context: 检索到的上下文文本。
        search_mode: 搜索模式 (local/global/hybrid)。
        entities_used: 使用的实体数量。
        communities_used: 使用的社区数量。
    """

    answer: str
    context: str
    search_mode: str
    entities_used: int = 0
    communities_used: int = 0


class GraphSearchService:
    """Graph RAG 搜索服务。

    提供基于知识图谱的 Local、Global 和 Hybrid 搜索能力。

    Example:
        >>> service = GraphSearchService()
        >>> result = await service.search(
        ...     session, query="智能手表有什么特点", category="digital"
        ... )
    """

    def __init__(self) -> None:
        """初始化搜索服务。"""
        self.settings = get_settings()
        self._llm: Any = None

    async def _get_llm(self) -> Any:
        """懒加载 LLM 客户端。

        Returns:
            LLM 客户端实例。
        """
        if self._llm is None:
            settings = self.settings
            if settings.llm_provider == "qwen":
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
            elif settings.llm_provider == "dashscope" and settings.effective_dashscope_api_key:
                from langchain_community.chat_models import ChatTongyi

                self._llm = ChatTongyi(
                    model=settings.llm_model,
                    dashscope_api_key=settings.effective_dashscope_api_key,
                    temperature=0,
                )
            else:
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
        return self._llm

    async def search(
        self,
        session: AsyncSession,
        query: str,
        category: str,
        *,
        mode: str | None = None,
        tenant_id: str | None = None,
    ) -> GraphSearchResult:
        """执行 Graph RAG 搜索。

        根据 mode 分发到 local/global/hybrid 搜索。

        Args:
            session: 数据库会话。
            query: 查询文本。
            category: 商品类目。
            mode: 搜索模式 (local/global/hybrid)，默认使用配置。
            tenant_id: 租户 ID（可选）。

        Returns:
            GraphSearchResult 搜索结果。
        """
        search_mode = mode or self.settings.graph_rag_search_mode

        if search_mode == "global":
            return await self._global_search(session, query, category, tenant_id=tenant_id)
        elif search_mode == "hybrid":
            return await self._hybrid_search(session, query, category, tenant_id=tenant_id)
        else:
            return await self._local_search(session, query, category, tenant_id=tenant_id)

    async def _local_search(
        self,
        session: AsyncSession,
        query: str,
        category: str,
        *,
        tenant_id: str | None = None,
    ) -> GraphSearchResult:
        """Local Search: 实体推理链。

        关键词匹配种子实体 -> 查询关系 -> 构建子图上下文 -> LLM 推理。

        Args:
            session: 数据库会话。
            query: 查询文本。
            category: 商品类目。
            tenant_id: 租户 ID（可选）。

        Returns:
            GraphSearchResult 搜索结果。
        """
        # 1. 关键词匹配种子实体
        keywords = [kw.strip() for kw in query.split() if len(kw.strip()) > 1]
        if not keywords:
            keywords = [query]

        tenant_condition = (
            (GraphRAGEntity.tenant_id == tenant_id)
            if tenant_id
            else GraphRAGEntity.tenant_id.is_(None)
        )

        seed_entities: list[GraphRAGEntity] = []
        for keyword in keywords:
            stmt = (
                select(GraphRAGEntity)
                .where(GraphRAGEntity.category == category)
                .where(tenant_condition)
                .where(
                    (GraphRAGEntity.name.ilike(f"%{keyword}%"))
                    | (GraphRAGEntity.description.ilike(f"%{keyword}%"))
                )
                .limit(5)
            )
            result = await session.execute(stmt)
            seed_entities.extend(result.scalars().all())

        # 去重
        seen_ids: set[int] = set()
        unique_entities: list[GraphRAGEntity] = []
        for entity in seed_entities:
            if entity.id not in seen_ids:
                seen_ids.add(entity.id)
                unique_entities.append(entity)

        if not unique_entities:
            return GraphSearchResult(
                answer="",
                context="未找到相关实体",
                search_mode="local",
                entities_used=0,
                communities_used=0,
            )

        # 2. 查询关系
        entity_ids = [e.id for e in unique_entities]
        edge_tenant_condition = (
            (GraphRAGEdge.tenant_id == tenant_id) if tenant_id else GraphRAGEdge.tenant_id.is_(None)
        )

        stmt = (
            select(GraphRAGEdge)
            .where(GraphRAGEdge.category == category)
            .where(edge_tenant_condition)
            .where(
                GraphRAGEdge.source_entity_id.in_(entity_ids)
                | GraphRAGEdge.target_entity_id.in_(entity_ids)
            )
            .limit(20)
        )
        result = await session.execute(stmt)
        edges = result.scalars().all()

        # 3. 构建子图上下文
        context_parts: list[str] = []
        context_parts.append("【相关实体】")
        for entity in unique_entities:
            context_parts.append(
                f"- {entity.name} ({entity.entity_type}): {entity.description or ''}"
            )

        context_parts.append("\n【关系线索】")
        entity_map = {e.id: e.name for e in unique_entities}
        for edge in edges:
            src_name = entity_map.get(edge.source_entity_id, f"Entity#{edge.source_entity_id}")
            tgt_name = entity_map.get(edge.target_entity_id, f"Entity#{edge.target_entity_id}")
            context_parts.append(f"- {src_name} --[{edge.relationship_type}]--> {tgt_name}")
            if edge.evidence:
                context_parts.append(f"  依据: {edge.evidence}")

        context = "\n".join(context_parts)

        # 4. LLM 推理
        prompt = (
            f"请根据以下知识图谱信息回答问题。\n\n"
            f"问题：{query}\n\n"
            f"知识图谱上下文：\n{context}\n\n"
            f"请基于以上信息给出准确、简洁的回答。如果信息不足，请说明。"
        )

        try:
            llm = await self._get_llm()
            response = await llm.ainvoke(prompt)
            answer = response.content.strip()
        except Exception as e:
            logger.warning(f"Local Search LLM 推理失败: {e}")
            answer = context

        return GraphSearchResult(
            answer=answer,
            context=context,
            search_mode="local",
            entities_used=len(unique_entities),
            communities_used=0,
        )

    async def _global_search(
        self,
        session: AsyncSession,
        query: str,
        category: str,
        *,
        tenant_id: str | None = None,
    ) -> GraphSearchResult:
        """Global Search: Map-Reduce 社区摘要。

        查询社区 -> 每个社区生成部分回答 -> 汇总。

        Args:
            session: 数据库会话。
            query: 查询文本。
            category: 商品类目。
            tenant_id: 租户 ID（可选）。

        Returns:
            GraphSearchResult 搜索结果。
        """
        # 1. 查询社区摘要
        tenant_condition = (
            (CommunitySummary.tenant_id == tenant_id)
            if tenant_id
            else CommunitySummary.tenant_id.is_(None)
        )

        max_communities = self.settings.graph_rag_global_search_max_communities
        stmt = (
            select(CommunitySummary)
            .where(CommunitySummary.category == category)
            .where(tenant_condition)
            .order_by(CommunitySummary.rank.desc())
            .limit(max_communities)
        )
        result = await session.execute(stmt)
        communities = result.scalars().all()

        if not communities:
            return GraphSearchResult(
                answer="",
                context="未找到相关社区摘要",
                search_mode="global",
                entities_used=0,
                communities_used=0,
            )

        # 2. Map: 每个社区生成部分回答
        partial_answers: list[str] = []
        context_parts: list[str] = []

        for community in communities:
            community_context = (
                f"社区: {community.title or community.community_id}\n{community.summary or ''}"
            )
            context_parts.append(community_context)

            prompt = (
                f"请根据以下社区摘要，回答问题。\n\n"
                f"问题：{query}\n\n"
                f"社区摘要：{community_context}\n\n"
                f"请给出与问题相关的部分回答。如果该社区信息与问题无关，请回复'无关'。"
            )

            try:
                llm = await self._get_llm()
                response = await llm.ainvoke(prompt)
                partial = response.content.strip()
                if partial and partial != "无关":
                    partial_answers.append(partial)
            except Exception as e:
                logger.warning(f"Global Search 社区 {community.community_id} 推理失败: {e}")

        # 3. Reduce: 汇总部分回答
        if not partial_answers:
            return GraphSearchResult(
                answer="",
                context="\n\n".join(context_parts),
                search_mode="global",
                entities_used=0,
                communities_used=len(communities),
            )

        combined = "\n\n".join([f"观点{i + 1}: {ans}" for i, ans in enumerate(partial_answers)])

        reduce_prompt = (
            f"请将以下多个观点整合为一个完整、连贯的回答。\n\n"
            f"问题：{query}\n\n"
            f"多个观点：\n{combined}\n\n"
            f"请给出综合回答。"
        )

        try:
            llm = await self._get_llm()
            response = await llm.ainvoke(reduce_prompt)
            answer = response.content.strip()
        except Exception as e:
            logger.warning(f"Global Search Reduce 推理失败: {e}")
            answer = combined

        return GraphSearchResult(
            answer=answer,
            context="\n\n".join(context_parts),
            search_mode="global",
            entities_used=0,
            communities_used=len(communities),
        )

    async def _hybrid_search(
        self,
        session: AsyncSession,
        query: str,
        category: str,
        *,
        tenant_id: str | None = None,
    ) -> GraphSearchResult:
        """Hybrid Search: 结合 Local + Global 结果。

        Args:
            session: 数据库会话。
            query: 查询文本。
            category: 商品类目。
            tenant_id: 租户 ID（可选）。

        Returns:
            GraphSearchResult 搜索结果。
        """
        local_result = await self._local_search(session, query, category, tenant_id=tenant_id)
        global_result = await self._global_search(session, query, category, tenant_id=tenant_id)

        # 合并上下文
        combined_context = f"=== Local Search ===\n{local_result.context}\n\n=== Global Search ===\n{global_result.context}"

        # 合并回答
        combined_answer_parts: list[str] = []
        if local_result.answer:
            combined_answer_parts.append(f"【局部推理】{local_result.answer}")
        if global_result.answer:
            combined_answer_parts.append(f"【全局推理】{global_result.answer}")

        combined_answer = "\n\n".join(combined_answer_parts)

        # 如果两个结果都有回答，尝试用 LLM 合并
        if local_result.answer and global_result.answer:
            merge_prompt = (
                f"请将以下局部推理和全局推理合并为一个完整、连贯的回答。\n\n"
                f"问题：{query}\n\n"
                f"局部推理：{local_result.answer}\n\n"
                f"全局推理：{global_result.answer}\n\n"
                f"请给出综合回答。"
            )

            try:
                llm = await self._get_llm()
                response = await llm.ainvoke(merge_prompt)
                combined_answer = response.content.strip()
            except Exception as e:
                logger.warning(f"Hybrid Search 合并推理失败: {e}")

        return GraphSearchResult(
            answer=combined_answer,
            context=combined_context,
            search_mode="hybrid",
            entities_used=local_result.entities_used,
            communities_used=global_result.communities_used,
        )


_graph_search: GraphSearchService | None = None


def get_graph_search() -> GraphSearchService:
    """获取 GraphSearchService 单例。

    Returns:
        GraphSearchService 实例。
    """
    global _graph_search
    if _graph_search is None:
        _graph_search = GraphSearchService()
    return _graph_search
