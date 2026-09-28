"""
KnowledgeRetriever 行为级测试。

Description:
    验证基础/高级检索管道的路径选择、多查询合并去重、
    场景化检索入口与类目记忆上下文的降级行为。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.retriever import (
    KnowledgeRetriever,
    RetrievalResult,
    get_knowledge_retriever,
)


def _create_search_result(chunk_id: int, content: str, similarity: float) -> SearchResult:
    """创建 SearchResult 辅助函数。

    Args:
        chunk_id: 分块 ID。
        content: 分块内容。
        similarity: 相似度。

    Returns:
        SearchResult 实例。
    """
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=chunk_id,
        content=content,
        similarity=similarity,
        metadata={},
        doc_title=f"文档{chunk_id}",
        doc_type="brand_guide",
    )


def _make_settings(**overrides: Any) -> MagicMock:
    """构造检索配置，默认关闭全部高级开关。

    Args:
        **overrides: 覆盖的配置项。

    Returns:
        配置 Mock。
    """
    settings = MagicMock()
    settings.query_rewriting_enabled = False
    settings.reranker_enabled = False
    settings.hybrid_retrieval_enabled = False
    settings.retrieval_top_k = 5
    settings.similarity_threshold = 0.0
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def _build_retriever(settings: MagicMock) -> KnowledgeRetriever:
    """构造带 Mock 依赖的 KnowledgeRetriever。

    Args:
        settings: 配置 Mock。

    Returns:
        KnowledgeRetriever 实例。
    """
    with (
        patch("src.rag.retriever.get_settings", return_value=settings),
        patch("src.rag.retriever.get_embedding_service"),
        patch("src.rag.retriever.VectorStore"),
    ):
        return KnowledgeRetriever()


def _wire_vector_backend(retriever: KnowledgeRetriever, results: list[SearchResult]) -> MagicMock:
    """注入 embedding 与向量检索后端。

    Args:
        retriever: 检索器实例。
        results: 向量检索返回的结果。

    Returns:
        向量存储 Mock。
    """
    mock_embedding = MagicMock()
    mock_embedding.aembed_single = AsyncMock(return_value=[0.1, 0.2])
    retriever.embedding_service = mock_embedding

    mock_vs = MagicMock()
    mock_vs.search = AsyncMock(return_value=results)
    retriever.vector_store = mock_vs
    return mock_vs


def _rewrite_result(*queries: str) -> MagicMock:
    """构造 QueryRewriter.rewrite 的返回值。

    Args:
        *queries: 改写后的查询列表。

    Returns:
        带 queries 属性的结果 Mock。
    """
    result = MagicMock()
    result.queries = list(queries)
    result.mode = "multi_query"
    return result


class TestAdvancedPipelinePaths:
    """高级管道的路径选择与降级。"""

    @pytest.mark.asyncio
    async def test_hybrid_enabled_routes_to_hybrid_retriever(self) -> None:
        """启用混合检索时走 HybridRetriever 而非纯向量。"""
        settings = _make_settings(hybrid_retrieval_enabled=True)
        retriever = _build_retriever(settings)
        mock_vs = _wire_vector_backend(retriever, [])

        hybrid_hits = [_create_search_result(7, "混合命中", 0.9)]
        mock_hybrid = MagicMock()
        mock_hybrid.search = AsyncMock(
            return_value=MagicMock(results=list(hybrid_hits), method="hybrid")
        )
        retriever._hybrid_retriever = mock_hybrid

        result = await retriever.retrieve(MagicMock(), "查询", tenant_id="t1")

        assert [r.chunk_id for r in result.results] == [7]
        assert result.query == "查询"
        mock_hybrid.search.assert_awaited_once()
        mock_vs.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_multi_query_results_are_merged_and_deduplicated(self) -> None:
        """多条改写查询的结果合并后按 chunk_id 去重。"""
        settings = _make_settings(query_rewriting_enabled=True, hybrid_retrieval_enabled=True)
        retriever = _build_retriever(settings)

        mock_rewriter = MagicMock()
        mock_rewriter.rewrite = AsyncMock(return_value=_rewrite_result("查询A", "查询B"))
        retriever._query_rewriter = mock_rewriter

        mock_hybrid = MagicMock()
        mock_hybrid.search = AsyncMock(
            side_effect=[
                MagicMock(
                    results=[
                        _create_search_result(1, "A-1", 0.9),
                        _create_search_result(2, "A-2", 0.8),
                    ]
                ),
                MagicMock(
                    results=[
                        _create_search_result(2, "B-2", 0.7),
                        _create_search_result(3, "B-3", 0.6),
                    ]
                ),
            ]
        )
        retriever._hybrid_retriever = mock_hybrid

        result = await retriever.retrieve(MagicMock(), "原始查询", tenant_id="t1")

        assert [r.chunk_id for r in result.results] == [1, 2, 3]
        assert mock_hybrid.search.await_count == 2
        # 第一条改写查询作为主查询
        assert mock_hybrid.search.await_args_list[0].args[1] == "查询A"

    @pytest.mark.asyncio
    async def test_multi_query_vector_path_merges_and_deduplicates(self) -> None:
        """纯向量模式下多查询结果同样合并去重。"""
        settings = _make_settings(query_rewriting_enabled=True)
        retriever = _build_retriever(settings)

        mock_rewriter = MagicMock()
        mock_rewriter.rewrite = AsyncMock(return_value=_rewrite_result("查询A", "查询B"))
        retriever._query_rewriter = mock_rewriter

        mock_vs = MagicMock()
        mock_vs.search = AsyncMock(
            side_effect=[
                [_create_search_result(1, "A-1", 0.9), _create_search_result(2, "A-2", 0.8)],
                [_create_search_result(2, "B-2", 0.7), _create_search_result(3, "B-3", 0.6)],
            ]
        )
        retriever.vector_store = mock_vs
        mock_embedding = MagicMock()
        mock_embedding.aembed_single = AsyncMock(return_value=[0.1])
        retriever.embedding_service = mock_embedding

        result = await retriever.retrieve(MagicMock(), "原始查询", tenant_id="t1")

        assert [r.chunk_id for r in result.results] == [1, 2, 3]
        assert mock_vs.search.await_count == 2

    @pytest.mark.asyncio
    async def test_rewrite_falls_back_to_original_query_when_empty(self) -> None:
        """改写结果为空时沿用原始查询。"""
        settings = _make_settings(query_rewriting_enabled=True)
        retriever = _build_retriever(settings)

        mock_rewriter = MagicMock()
        mock_rewriter.rewrite = AsyncMock(return_value=_rewrite_result())
        retriever._query_rewriter = mock_rewriter

        mock_vs = _wire_vector_backend(retriever, [_create_search_result(1, "内容", 0.5)])

        result = await retriever.retrieve(MagicMock(), "原始查询", tenant_id="t1")

        assert result.query == "原始查询"
        assert mock_vs.search.await_count == 1

    @pytest.mark.asyncio
    async def test_reranker_applied_in_advanced_pipeline(self) -> None:
        """启用重排序时最终结果以重排序输出为准。"""
        settings = _make_settings(reranker_enabled=True)
        retriever = _build_retriever(settings)
        _wire_vector_backend(retriever, [_create_search_result(1, "内容", 0.5)])

        from src.rag.reranker import RerankResult

        reranked = [_create_search_result(9, "重排后", 0.99)]
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(
            return_value=RerankResult(results=reranked, original_count=1, reranked_count=1)
        )
        retriever._reranker = mock_reranker

        result = await retriever.retrieve(MagicMock(), "查询", tenant_id="t1")

        assert [r.chunk_id for r in result.results] == [9]
        mock_reranker.rerank.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reranker_skipped_when_disabled(self) -> None:
        """重排序关闭时不做重排。"""
        settings = _make_settings(query_rewriting_enabled=True, reranker_enabled=False)
        retriever = _build_retriever(settings)

        mock_rewriter = MagicMock()
        mock_rewriter.rewrite = AsyncMock(return_value=_rewrite_result("查询"))
        retriever._query_rewriter = mock_rewriter

        mock_vs = _wire_vector_backend(retriever, [_create_search_result(1, "内容", 0.5)])
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock()
        retriever._reranker = mock_reranker

        result = await retriever.retrieve(MagicMock(), "查询", tenant_id="t1")

        assert [r.chunk_id for r in result.results] == [1]
        mock_reranker.rerank.assert_not_awaited()
        assert mock_vs.search.await_count == 1


class TestContextAndSources:
    """上下文与来源构建行为。"""

    @pytest.mark.asyncio
    async def test_context_and_sources_built_from_results(self) -> None:
        """检索结果被拼进上下文并抽取来源。"""
        settings = _make_settings()
        retriever = _build_retriever(settings)
        hits = [
            _create_search_result(1, "内容甲", 0.9),
            _create_search_result(2, "内容乙", 0.8),
        ]
        _wire_vector_backend(retriever, hits)

        result = await retriever.retrieve(MagicMock(), "查询", tenant_id="t1")

        assert "内容甲" in result.context
        assert "内容乙" in result.context
        assert "---" in result.context
        assert [s["chunk_id"] for s in result.sources] == [1, 2]
        assert result.sources[0]["doc_title"] == "文档1"
        assert result.sources[0]["similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_empty_results_yield_empty_context(self) -> None:
        """无命中时上下文为空字符串。"""
        settings = _make_settings()
        retriever = _build_retriever(settings)
        _wire_vector_backend(retriever, [])

        result = await retriever.retrieve(MagicMock(), "查询", tenant_id="t1")

        assert result.context == ""
        assert result.sources == []


class TestScenarioRetrieval:
    """场景化检索入口的查询编排与合并。"""

    def _install_recording_retrieve(
        self,
        retriever: KnowledgeRetriever,
        hits_by_keyword: dict[str, list[SearchResult]],
    ) -> list[str]:
        """替换 retrieve 为记录调用的假实现。

        Args:
            retriever: 检索器实例。
            hits_by_keyword: 关键字到结果列表的映射。

        Returns:
            记录查询的列表。
        """
        calls: list[str] = []

        async def fake_retrieve(session: Any, query: str, **kwargs: Any) -> RetrievalResult:
            calls.append(query)
            hits = next(
                (v for k, v in hits_by_keyword.items() if k in query),
                [_create_search_result(1, "默认", 0.5)],
            )
            return RetrievalResult(query=query, results=list(hits), context="", sources=[])

        retriever.retrieve = fake_retrieve  # type: ignore[method-assign]
        return calls

    @pytest.mark.asyncio
    async def test_product_analysis_merges_category_brand_and_case(self) -> None:
        """商品分析合并分类、品牌与案例结果并去重。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever,
            {
                "卖点模板": [
                    _create_search_result(1, "分类知识", 0.9),
                    _create_search_result(2, "共享", 0.8),
                ],
                "品牌规范": [
                    _create_search_result(2, "共享", 0.8),
                    _create_search_result(3, "品牌规范", 0.7),
                ],
                "成功案例": [_create_search_result(4, "案例", 0.6)],
            },
        )

        result = await retriever.retrieve_for_product_analysis(
            MagicMock(), "智能手表", "digital", brand="Acme", tenant_id="t1"
        )

        assert result.query == "分析商品: 智能手表"
        assert [r.chunk_id for r in result.results] == [1, 2, 3, 4]
        assert len(calls) == 3
        assert any("digital" in q for q in calls)
        assert any("Acme" in q for q in calls)

    @pytest.mark.asyncio
    async def test_product_analysis_skips_brand_lookup_without_brand(self) -> None:
        """未提供品牌时不检索品牌规范。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever, {"卖点模板": [_create_search_result(1, "分类", 0.9)]}
        )

        result = await retriever.retrieve_for_product_analysis(
            MagicMock(), "智能手表", "digital", tenant_id="t1"
        )

        assert len(calls) == 2
        assert not any("品牌规范" in q for q in calls)
        assert result.results

    @pytest.mark.asyncio
    async def test_creative_planning_queries_brand_and_style(self) -> None:
        """创意策划检索品牌视觉规范与风格模板。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever,
            {
                "视觉规范": [_create_search_result(1, "品牌视觉", 0.9)],
                "创意风格": [_create_search_result(2, "风格", 0.8)],
            },
        )

        result = await retriever.retrieve_for_creative_planning(
            MagicMock(), "digital", brand="Acme", style_preference="极简", tenant_id="t1"
        )

        assert result.query == "创意策划: digital"
        assert [r.chunk_id for r in result.results] == [1, 2]
        assert len(calls) == 2
        assert any("Acme" in q for q in calls)
        assert any("极简" in q for q in calls)

    @pytest.mark.asyncio
    async def test_creative_planning_without_brand_skips_brand_query(self) -> None:
        """无品牌时创意策划只检索风格模板。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever, {"创意风格": [_create_search_result(2, "风格", 0.8)]}
        )

        await retriever.retrieve_for_creative_planning(MagicMock(), "digital", tenant_id="t1")

        assert len(calls) == 1
        assert "创意风格" in calls[0]

    @pytest.mark.asyncio
    async def test_image_generation_queries_brand_style_and_category(self) -> None:
        """图片生成合并品牌、风格与类目知识三路结果。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever,
            {
                "构图规则": [_create_search_result(1, "品牌视觉", 0.9)],
                "图片风格": [_create_search_result(2, "风格", 0.8)],
                "产品摄影": [_create_search_result(3, "类目知识", 0.7)],
            },
        )

        result = await retriever.retrieve_for_image_generation(
            MagicMock(), "digital", brand="Acme", tenant_id="t1"
        )

        assert result.query == "图片生成: digital"
        assert [r.chunk_id for r in result.results] == [1, 2, 3]
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_image_generation_without_brand_skips_brand_query(self) -> None:
        """无品牌时图片生成只检索风格与类目知识。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(
            retriever,
            {
                "图片风格": [_create_search_result(2, "风格", 0.8)],
                "产品摄影": [_create_search_result(3, "类目知识", 0.7)],
            },
        )

        await retriever.retrieve_for_image_generation(MagicMock(), "digital", tenant_id="t1")

        assert len(calls) == 2

    @pytest.mark.asyncio
    async def test_compliance_rules_use_content_as_query(self) -> None:
        """传入 content 时用作合规检索查询。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(retriever, {})

        await retriever.retrieve_compliance_rules(MagicMock(), "限时秒杀绝对第一", tenant_id="t1")

        assert calls == ["限时秒杀绝对第一"]

    @pytest.mark.asyncio
    async def test_compliance_rules_use_default_query_without_content(self) -> None:
        """未传 content 时使用默认合规查询。"""
        retriever = _build_retriever(_make_settings())
        calls = self._install_recording_retrieve(retriever, {})

        await retriever.retrieve_compliance_rules(MagicMock(), tenant_id="t1")

        assert len(calls) == 1
        assert "合规规则" in calls[0]


class TestCategoryMemoryContext:
    """类目记忆上下文检索与降级。"""

    @pytest.mark.asyncio
    async def test_returns_empty_string_when_no_data(self) -> None:
        """实体/边/记忆全空时返回空字符串。"""
        from src.rag.graph_memory import GraphMemoryContext

        retriever = _build_retriever(_make_settings())
        context = GraphMemoryContext(category="digital")

        with patch("src.rag.graph_memory.GraphMemoryService") as mock_service:
            mock_service.return_value.build_category_context = AsyncMock(return_value=context)
            result = await retriever.retrieve_category_memory_context(
                MagicMock(), "digital", tenant_id="t1"
            )

        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_formatted_context_when_data_exists(self) -> None:
        """有实体数据时返回格式化上下文。"""
        from src.rag.graph_memory import GraphMemoryContext

        retriever = _build_retriever(_make_settings())
        context = GraphMemoryContext(
            category="digital", entities=[{"name": "智能手表", "entity_type": "产品"}]
        )

        with patch("src.rag.graph_memory.GraphMemoryService") as mock_service:
            instance = mock_service.return_value
            instance.build_category_context = AsyncMock(return_value=context)
            instance.format_context = MagicMock(return_value="实体: 智能手表")
            result = await retriever.retrieve_category_memory_context(
                MagicMock(), "digital", limit=5, tenant_id="t1"
            )

        assert result == "实体: 智能手表"
        instance.format_context.assert_called_once_with(context)

    @pytest.mark.asyncio
    async def test_import_failure_returns_empty_string(self) -> None:
        """GraphMemoryService 不可用时降级为空字符串。"""
        retriever = _build_retriever(_make_settings())

        with patch.dict("sys.modules", {"src.rag.graph_memory": None}):
            result = await retriever.retrieve_category_memory_context(
                MagicMock(), "digital", tenant_id="t1"
            )

        assert result == ""


class TestLazyServiceAccessors:
    """懒加载服务属性。"""

    def test_query_rewriter_property_lazily_loads(self) -> None:
        """query_rewriter 属性触发懒加载。"""
        retriever = _build_retriever(_make_settings())
        assert retriever._query_rewriter is None

        with patch(
            "src.rag.query_rewriter.get_query_rewriter",
            return_value=MagicMock(name="rewriter"),
        ) as factory:
            first = retriever.query_rewriter
            second = retriever.query_rewriter

        assert first is second
        factory.assert_called_once()

    def test_reranker_property_lazily_loads(self) -> None:
        """reranker 属性触发懒加载。"""
        retriever = _build_retriever(_make_settings())
        assert retriever._reranker is None

        with patch(
            "src.rag.reranker.get_reranker",
            return_value=MagicMock(name="reranker"),
        ) as factory:
            first = retriever.reranker
            second = retriever.reranker

        assert first is second
        factory.assert_called_once()

    def test_hybrid_retriever_property_lazily_loads(self) -> None:
        """hybrid_retriever 属性触发懒加载。"""
        retriever = _build_retriever(_make_settings())
        assert retriever._hybrid_retriever is None

        with patch(
            "src.rag.hybrid_retriever.get_hybrid_retriever",
            return_value=MagicMock(name="hybrid"),
        ) as factory:
            first = retriever.hybrid_retriever
            second = retriever.hybrid_retriever

        assert first is second
        factory.assert_called_once()


class TestGetKnowledgeRetriever:
    """get_knowledge_retriever 单例行为。"""

    def test_returns_singleton(self) -> None:
        """重复调用返回同一实例。"""
        import src.rag.retriever as retriever_module

        original = retriever_module._knowledge_retriever
        try:
            retriever_module._knowledge_retriever = None
            first = get_knowledge_retriever()
            second = get_knowledge_retriever()
            assert first is second
        finally:
            retriever_module._knowledge_retriever = original
