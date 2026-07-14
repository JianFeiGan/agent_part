"""
GraphSearchService 测试。

Description:
    测试 Graph RAG 的 Local Search、Global Search 和 Hybrid Search 功能。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.graph_search import GraphSearchResult, GraphSearchService


class TestLocalSearch:
    """Local Search 测试类。"""

    @pytest.fixture
    def service(self) -> GraphSearchService:
        """创建测试用搜索服务实例。"""
        return GraphSearchService()

    @pytest.mark.asyncio
    async def test_local_search(self, service: GraphSearchService) -> None:
        """测试 Local Search 基本流程。"""
        # 构造 mock 实体
        mock_entity = MagicMock()
        mock_entity.id = 1
        mock_entity.name = "智能手表"
        mock_entity.entity_type = "产品"
        mock_entity.description = "具有健康监测功能的智能手表"

        # 构造 mock 边
        mock_edge = MagicMock()
        mock_edge.source_entity_id = 1
        mock_edge.target_entity_id = 2
        mock_edge.relationship_type = "具有功能"
        mock_edge.evidence = "智能手表具有健康监测功能"

        # Mock 数据库查询
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_entity])

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # 第二次 execute 返回边
        mock_edge_scalars = MagicMock()
        mock_edge_scalars.all = MagicMock(return_value=[mock_edge])

        mock_edge_result = MagicMock()
        mock_edge_result.scalars = MagicMock(return_value=mock_edge_scalars)

        # 交替返回实体查询和边查询
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_edge_result])

        # Mock LLM
        mock_llm_response = MagicMock()
        mock_llm_response.content = "智能手表是一款具有健康监测功能的产品"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        with patch.object(service, "_get_llm", return_value=mock_llm):
            result = await service._local_search(
                mock_session, query="智能手表有什么功能", category="digital"
            )

        assert result.search_mode == "local"
        assert result.entities_used == 1
        assert "智能手表" in result.context

    @pytest.mark.asyncio
    async def test_local_search_no_entities(self, service: GraphSearchService) -> None:
        """测试 Local Search 未找到实体时返回空结果。"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._local_search(mock_session, query="不存在的实体", category="digital")

        assert result.entities_used == 0
        assert result.answer == ""


class TestGlobalSearch:
    """Global Search 测试类。"""

    @pytest.fixture
    def service(self) -> GraphSearchService:
        """创建测试用搜索服务实例。"""
        return GraphSearchService()

    @pytest.mark.asyncio
    async def test_global_search(self, service: GraphSearchService) -> None:
        """测试 Global Search 基本流程。"""
        # 构造 mock 社区摘要
        mock_community = MagicMock()
        mock_community.community_id = "comm_0"
        mock_community.title = "智能穿戴社区"
        mock_community.summary = "包含智能手表、手环等穿戴设备"

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_community])

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        # Mock LLM (Map + Reduce 两次调用)
        mock_map_response = MagicMock()
        mock_map_response.content = "智能穿戴设备具有健康监测功能"

        mock_reduce_response = MagicMock()
        mock_reduce_response.content = "智能穿戴设备主要特点包括健康监测功能"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=[mock_map_response, mock_reduce_response])

        with patch.object(service, "_get_llm", return_value=mock_llm):
            result = await service._global_search(
                mock_session, query="穿戴设备特点", category="digital"
            )

        assert result.search_mode == "global"
        assert result.communities_used == 1

    @pytest.mark.asyncio
    async def test_global_search_no_communities(self, service: GraphSearchService) -> None:
        """测试 Global Search 未找到社区时返回空结果。"""
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._global_search(mock_session, query="测试查询", category="digital")

        assert result.communities_used == 0
        assert result.answer == ""


class TestHybridSearch:
    """Hybrid Search 测试类。"""

    @pytest.fixture
    def service(self) -> GraphSearchService:
        """创建测试用搜索服务实例。"""
        return GraphSearchService()

    @pytest.mark.asyncio
    async def test_hybrid_search(self, service: GraphSearchService) -> None:
        """测试 Hybrid Search 结合 Local + Global 结果。"""
        local_result = GraphSearchResult(
            answer="局部推理结果",
            context="Local context",
            search_mode="local",
            entities_used=3,
            communities_used=0,
        )

        global_result = GraphSearchResult(
            answer="全局推理结果",
            context="Global context",
            search_mode="global",
            entities_used=0,
            communities_used=2,
        )

        # Mock LLM 合并
        mock_merge_response = MagicMock()
        mock_merge_response.content = "综合回答"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_merge_response)

        with (
            patch.object(service, "_local_search", return_value=local_result),
            patch.object(service, "_global_search", return_value=global_result),
            patch.object(service, "_get_llm", return_value=mock_llm),
        ):
            result = await service._hybrid_search(AsyncMock(), query="测试查询", category="digital")

        assert result.search_mode == "hybrid"
        assert result.entities_used == 3
        assert result.communities_used == 2
