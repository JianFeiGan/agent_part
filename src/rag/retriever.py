"""
知识检索器。

Description:
    封装 RAG 检索逻辑，为 Agent 提供知识增强能力。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.vector_store import SearchResult, VectorStore
from src.rag.embeddings import EmbeddingService, get_embedding_service

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """检索结果。

    Attributes:
        query: 原始查询。
        results: 搜索结果列表。
        context: 构建的上下文文本。
        sources: 来源引用列表。
    """

    query: str
    results: list[SearchResult]
    context: str
    sources: list[dict[str, Any]]


class KnowledgeRetriever:
    """知识检索器。

    为 Agent 提供知识检索能力。

    Example:
        >>> retriever = KnowledgeRetriever()
        >>> result = await retriever.retrieve(
        ...     session,
        ...     query="智能手表产品特点",
        ...     doc_type="category_knowledge",
        ...     category="digital"
        ... )
        >>> print(result.context)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        """初始化知识检索器。

        Args:
            embedding_service: Embedding 服务实例。
            vector_store: 向量存储实例。
        """
        self.settings = get_settings()
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or VectorStore()

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        doc_type: str | None = None,
        category: str | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> RetrievalResult:
        """检索相关知识。

        Args:
            session: 数据库会话。
            query: 查询文本。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。
            top_k: 返回结果数量。
            similarity_threshold: 相似度阈值。

        Returns:
            检索结果。
        """
        # 生成查询向量
        query_embedding = self.embedding_service.embed_single(query)

        # 执行向量检索
        results = await self.vector_store.search(
            session,
            query_embedding,
            top_k=top_k,
            doc_type=doc_type,
            category=category,
            similarity_threshold=similarity_threshold,
        )

        # 构建上下文
        context = self._build_context(results)

        # 提取来源信息
        sources = self._extract_sources(results)

        logger.info(
            f"Retrieval completed: query='{query[:50]}...', "
            f"results={len(results)}, doc_type={doc_type}"
        )

        return RetrievalResult(
            query=query,
            results=results,
            context=context,
            sources=sources,
        )

    async def retrieve_for_product_analysis(
        self,
        session: AsyncSession,
        product_name: str,
        category: str,
        brand: str | None = None,
    ) -> RetrievalResult:
        """为商品分析检索知识。

        检索商品分类知识和品牌规范。

        Args:
            session: 数据库会话。
            product_name: 商品名称。
            category: 商品类目。
            brand: 品牌名称。

        Returns:
            检索结果。
        """
        results_list = []

        # 1. 检索分类知识
        category_result = await self.retrieve(
            session,
            query=f"{category} 商品特点 卖点模板",
            doc_type="category_knowledge",
            category=category,
            top_k=3,
        )
        results_list.extend(category_result.results)

        # 2. 检索品牌规范（如果有）
        if brand:
            brand_result = await self.retrieve(
                session,
                query=f"{brand} 品牌规范 术语",
                doc_type="brand_guide",
                top_k=2,
            )
            results_list.extend(brand_result.results)

        # 3. 检索历史案例
        case_result = await self.retrieve(
            session,
            query=f"{product_name} {category} 成功案例",
            doc_type="case_study",
            category=category,
            top_k=3,
        )
        results_list.extend(case_result.results)

        # 去重并构建结果
        unique_results = self._deduplicate_results(results_list)
        context = self._build_context(unique_results)
        sources = self._extract_sources(unique_results)

        return RetrievalResult(
            query=f"分析商品: {product_name}",
            results=unique_results,
            context=context,
            sources=sources,
        )

    async def retrieve_for_creative_planning(
        self,
        session: AsyncSession,
        category: str,
        brand: str | None = None,
        style_preference: str | None = None,
    ) -> RetrievalResult:
        """为创意策划检索知识。

        检索品牌视觉规范和成功创意案例。

        Args:
            session: 数据库会话。
            category: 商品类目。
            brand: 品牌名称。
            style_preference: 风格偏好。

        Returns:
            检索结果。
        """
        results_list = []

        # 1. 检索品牌视觉规范
        if brand:
            brand_result = await self.retrieve(
                session,
                query=f"{brand} 视觉规范 配色",
                doc_type="brand_guide",
                top_k=3,
            )
            results_list.extend(brand_result.results)

        # 2. 检索风格模板
        style_query = f"{category} {style_preference or ''} 创意风格 视觉设计"
        style_result = await self.retrieve(
            session,
            query=style_query,
            doc_type="case_study",
            category=category,
            top_k=5,
        )
        results_list.extend(style_result.results)

        unique_results = self._deduplicate_results(results_list)
        context = self._build_context(unique_results)
        sources = self._extract_sources(unique_results)

        return RetrievalResult(
            query=f"创意策划: {category}",
            results=unique_results,
            context=context,
            sources=sources,
        )

    async def retrieve_compliance_rules(
        self,
        session: AsyncSession,
        content: str | None = None,
    ) -> RetrievalResult:
        """检索合规规则。

        Args:
            session: 数据库会话。
            content: 待检查的内容（用于关键词匹配）。

        Returns:
            检索结果。
        """
        query = content or "禁止词 敏感内容 合规规则"
        result = await self.retrieve(
            session,
            query=query,
            doc_type="compliance_rule",
            top_k=5,
        )
        return result

    def _build_context(self, results: list[SearchResult]) -> str:
        """构建上下文文本。

        Args:
            results: 搜索结果列表。

        Returns:
            上下文文本。
        """
        if not results:
            return ""

        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(
                f"[{i}] 来源: {result.doc_title}\n"
                f"类型: {result.doc_type}\n"
                f"相似度: {result.similarity:.3f}\n"
                f"内容: {result.content}\n"
            )

        return "\n---\n".join(context_parts)

    def _extract_sources(self, results: list[SearchResult]) -> list[dict[str, Any]]:
        """提取来源信息。

        Args:
            results: 搜索结果列表。

        Returns:
            来源信息列表。
        """
        return [
            {
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "doc_title": r.doc_title,
                "doc_type": r.doc_type,
                "similarity": r.similarity,
            }
            for r in results
        ]

    def _deduplicate_results(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """去除重复结果。

        Args:
            results: 搜索结果列表。

        Returns:
            去重后的结果列表。
        """
        seen_chunk_ids = set()
        unique_results = []

        for result in results:
            if result.chunk_id not in seen_chunk_ids:
                seen_chunk_ids.add(result.chunk_id)
                unique_results.append(result)

        return unique_results


# 全局知识检索器实例
_knowledge_retriever: KnowledgeRetriever | None = None


def get_knowledge_retriever() -> KnowledgeRetriever:
    """获取知识检索器单例。

    Returns:
        知识检索器实例。
    """
    global _knowledge_retriever

    if _knowledge_retriever is None:
        _knowledge_retriever = KnowledgeRetriever()

    return _knowledge_retriever
