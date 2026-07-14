"""
知识检索器。

Description:
    封装 RAG 检索逻辑，为 Agent 提供知识增强能力。
    支持高级 RAG 管道：Query 改写 → 混合检索/向量检索 → 重排序。
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.vector_store import SearchResult, VectorStore
from src.rag.embeddings import EmbeddingService, get_embedding_service

if TYPE_CHECKING:
    from src.rag.hybrid_retriever import HybridRetriever
    from src.rag.query_rewriter import QueryRewriter
    from src.rag.reranker import CrossEncoderReranker

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

    为 Agent 提供知识检索能力。支持高级 RAG 管道：
    Query 改写 → 混合检索/向量检索 → 重排序。

    Example:
        >>> retriever = KnowledgeRetriever()
        >>> result = await retriever.retrieve(
        ...     session,
        ...     query="智能手表产品特点",
        ...     doc_type="category_knowledge",
        ...     category="digital",
        ...     tenant_id="t1",
        ... )
        >>> print(result.context)
    """

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
        query_rewriter: "QueryRewriter | None" = None,
        reranker: "CrossEncoderReranker | None" = None,
        hybrid_retriever: "HybridRetriever | None" = None,
    ) -> None:
        """初始化知识检索器。

        Args:
            embedding_service: Embedding 服务实例。
            vector_store: 向量存储实例。
            query_rewriter: Query 改写服务实例。
            reranker: 重排序服务实例。
            hybrid_retriever: 混合检索服务实例。
        """
        self.settings = get_settings()
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or VectorStore()
        self._query_rewriter = query_rewriter
        self._reranker = reranker
        self._hybrid_retriever = hybrid_retriever

    @property
    def query_rewriter(self) -> "QueryRewriter":
        """懒加载 Query 改写服务。

        Returns:
            QueryRewriter 实例。
        """
        if self._query_rewriter is None:
            from src.rag.query_rewriter import get_query_rewriter

            self._query_rewriter = get_query_rewriter()
        return self._query_rewriter

    @property
    def reranker(self) -> "CrossEncoderReranker":
        """懒加载重排序服务。

        Returns:
            CrossEncoderReranker 实例。
        """
        if self._reranker is None:
            from src.rag.reranker import get_reranker

            self._reranker = get_reranker()
        return self._reranker

    @property
    def hybrid_retriever(self) -> "HybridRetriever":
        """懒加载混合检索服务。

        Returns:
            HybridRetriever 实例。
        """
        if self._hybrid_retriever is None:
            from src.rag.hybrid_retriever import get_hybrid_retriever

            self._hybrid_retriever = get_hybrid_retriever()
        return self._hybrid_retriever

    def _is_advanced_rag_enabled(self) -> bool:
        """检查是否启用高级 RAG 管道。

        Returns:
            是否启用任一高级功能。
        """
        return (
            self.settings.query_rewriting_enabled
            or self.settings.reranker_enabled
            or self.settings.hybrid_retrieval_enabled
        )

    async def _retrieve_advanced(
        self,
        session: AsyncSession,
        query: str,
        doc_type: str | None = None,
        category: str | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        *,
        tenant_id: str,
    ) -> RetrievalResult:
        """高级 RAG 管道检索。

        流程：Query 改写 → 混合检索/向量检索 → 重排序 → 构建上下文。

        Args:
            session: 数据库会话。
            query: 查询文本。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。
            top_k: 返回结果数量。
            similarity_threshold: 相似度阈值。
            tenant_id: 租户 ID。

        Returns:
            检索结果。
        """
        # 1. Query 改写
        if self.settings.query_rewriting_enabled:
            rewrite_result = await self.query_rewriter.rewrite(query)
            # 使用第一个改写查询作为主查询
            effective_query = rewrite_result.queries[0] if rewrite_result.queries else query
            all_queries = rewrite_result.queries
            logger.info(
                f"Query 改写: 原始='{query[:50]}...', "
                f"改写后={len(all_queries)} 条, 模式={rewrite_result.mode}"
            )
        else:
            effective_query = query
            all_queries = [query]

        # 2. 检索
        if self.settings.hybrid_retrieval_enabled:
            # 混合检索
            hybrid_result = await self.hybrid_retriever.search(
                session,
                effective_query,
                tenant_id=tenant_id,
                top_k=top_k,
                doc_type=doc_type,
                category=category,
                similarity_threshold=similarity_threshold,
            )
            results = hybrid_result.results
            retrieval_method = "hybrid"

            # 如果有多个改写查询，对每个额外查询也执行检索并合并
            if len(all_queries) > 1:
                for extra_query in all_queries[1:]:
                    extra_result = await self.hybrid_retriever.search(
                        session,
                        extra_query,
                        tenant_id=tenant_id,
                        top_k=top_k or self.settings.retrieval_top_k,
                        doc_type=doc_type,
                        category=category,
                        similarity_threshold=similarity_threshold,
                    )
                    results.extend(extra_result.results)

                # 去重
                results = self._deduplicate_results(results)
        else:
            # 纯向量检索
            query_embedding = await self.embedding_service.aembed_single(effective_query)
            results = await self.vector_store.search(
                session,
                query_embedding,
                top_k=top_k,
                doc_type=doc_type,
                category=category,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id,
            )
            retrieval_method = "vector"

            # 如果有多个改写查询，对每个额外查询也执行检索并合并
            if len(all_queries) > 1:
                for extra_query in all_queries[1:]:
                    extra_embedding = await self.embedding_service.aembed_single(extra_query)
                    extra_results = await self.vector_store.search(
                        session,
                        extra_embedding,
                        top_k=top_k or self.settings.retrieval_top_k,
                        doc_type=doc_type,
                        category=category,
                        similarity_threshold=similarity_threshold,
                        tenant_id=tenant_id,
                    )
                    results.extend(extra_results)

                # 去重
                results = self._deduplicate_results(results)

        # 3. 重排序
        if self.settings.reranker_enabled:
            rerank_result = await self.reranker.rerank(query, results, top_k=top_k)
            results = rerank_result.results
            logger.info(
                f"重排序完成: 原始 {rerank_result.original_count} 条 -> "
                f"保留 {rerank_result.reranked_count} 条"
            )

        # 4. 构建上下文
        context = self._build_context(results)
        sources = self._extract_sources(results)

        logger.info(
            f"高级 RAG 检索完成: query='{query[:50]}...', "
            f"results={len(results)}, method={retrieval_method}"
        )

        return RetrievalResult(
            query=query,
            results=results,
            context=context,
            sources=sources,
        )

    async def retrieve(
        self,
        session: AsyncSession,
        query: str,
        doc_type: str | None = None,
        category: str | None = None,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
        *,
        tenant_id: str,
    ) -> RetrievalResult:
        """检索相关知识。

        当高级 RAG 功能启用时自动走高级管道，否则走原有逻辑。

        Args:
            session: 数据库会话。
            query: 查询文本。
            doc_type: 文档类型过滤。
            category: 商品类目过滤。
            top_k: 返回结果数量。
            similarity_threshold: 相似度阈值。
            tenant_id: 租户 ID。

        Returns:
            检索结果。
        """
        # 高级 RAG 管道
        if self._is_advanced_rag_enabled():
            return await self._retrieve_advanced(
                session,
                query,
                doc_type=doc_type,
                category=category,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                tenant_id=tenant_id,
            )

        # 基础向量检索
        # 生成查询向量
        query_embedding = await self.embedding_service.aembed_single(query)

        # 执行向量检索
        results = await self.vector_store.search(
            session,
            query_embedding,
            top_k=top_k,
            doc_type=doc_type,
            category=category,
            similarity_threshold=similarity_threshold,
            tenant_id=tenant_id,
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
        *,
        tenant_id: str,
    ) -> RetrievalResult:
        """为商品分析检索知识。

        检索商品分类知识和品牌规范。

        Args:
            session: 数据库会话。
            product_name: 商品名称。
            category: 商品类目。
            brand: 品牌名称。
            tenant_id: 租户 ID。

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
            tenant_id=tenant_id,
        )
        results_list.extend(category_result.results)

        # 2. 检索品牌规范（如果有）
        if brand:
            brand_result = await self.retrieve(
                session,
                query=f"{brand} 品牌规范 术语",
                doc_type="brand_guide",
                top_k=2,
                tenant_id=tenant_id,
            )
            results_list.extend(brand_result.results)

        # 3. 检索历史案例
        case_result = await self.retrieve(
            session,
            query=f"{product_name} {category} 成功案例",
            doc_type="case_study",
            category=category,
            top_k=3,
            tenant_id=tenant_id,
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
        *,
        tenant_id: str,
    ) -> RetrievalResult:
        """为创意策划检索知识。

        检索品牌视觉规范和成功创意案例。

        Args:
            session: 数据库会话。
            category: 商品类目。
            brand: 品牌名称。
            style_preference: 风格偏好。
            tenant_id: 租户 ID。

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
                tenant_id=tenant_id,
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
            tenant_id=tenant_id,
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
        *,
        tenant_id: str,
    ) -> RetrievalResult:
        """检索合规规则。

        Args:
            session: 数据库会话。
            content: 待检查的内容（用于关键词匹配）。
            tenant_id: 租户 ID。

        Returns:
            检索结果。
        """
        query = content or "禁止词 敏感内容 合规规则"
        result = await self.retrieve(
            session,
            query=query,
            doc_type="compliance_rule",
            top_k=5,
            tenant_id=tenant_id,
        )
        return result

    async def retrieve_category_memory_context(
        self,
        session: AsyncSession,
        category: str,
        limit: int = 20,
        *,
        tenant_id: str | None = None,
    ) -> str:
        """检索类目记忆上下文。

        从 Graph RAG 实体/边和 CategoryMemory 表获取类目知识上下文，
        并格式化为可读字符串。空上下文返回空字符串 ""。

        Args:
            session: 数据库会话。
            category: 商品类目。
            limit: 实体返回数量限制。
            tenant_id: 租户 ID（可选）。

        Returns:
            格式化后的上下文字符串，无数据时返回空字符串。
        """
        try:
            from src.rag.graph_memory import GraphMemoryService

            service = GraphMemoryService()
            context = await service.build_category_context(
                session, category, limit=limit, tenant_id=tenant_id
            )

            # 如果没有任何数据则返回空字符串
            if not context.entities and not context.edges and context.category_memory is None:
                return ""

            return service.format_context(context)
        except ImportError as e:
            logger.warning(f"GraphMemoryService not available: {e}")
            return ""

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
