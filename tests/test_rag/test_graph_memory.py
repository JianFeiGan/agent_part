"""
Graph Memory 服务测试。

Description:
    测试 GraphMemoryService 查询和格式化能力。
@author ganjianfei
@version 1.0.0
2026-06-12
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models import CategoryMemory, GraphRAGEdge, GraphRAGEntity
from src.rag.graph_memory import GraphMemoryContext, GraphMemoryService


def _create_entity(
    id_: int,
    name: str = "test",
    category: str = "digital",
    entity_type: str = "concept",
    description: str | None = None,
    aliases: list | None = None,
) -> GraphRAGEntity:
    """创建测试用实体。"""
    return GraphRAGEntity(
        id=id_,
        name=name,
        category=category,
        entity_type=entity_type,
        description=description,
        aliases=aliases or [],
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _create_edge(
    id_: int,
    source_entity_id: int = 1,
    target_entity_id: int = 2,
    relationship_type: str = "related_to",
    category: str = "digital",
    weight: float = 1.0,
    evidence: str | None = None,
) -> GraphRAGEdge:
    """创建测试用边。"""
    return GraphRAGEdge(
        id=id_,
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        relationship_type=relationship_type,
        category=category,
        weight=weight,
        evidence=evidence,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


def _create_category_memory(
    id_: int,
    category: str = "digital",
    summary: str | None = None,
    best_practices: list[str] | None = None,
    negative_patterns: list[str] | None = None,
    style_guidelines: dict[str, str] | None = None,
    performance_hints: dict[str, str] | None = None,
) -> CategoryMemory:
    """创建测试用类目记忆。"""
    return CategoryMemory(
        id=id_,
        category=category,
        summary=summary,
        best_practices=best_practices or [],
        negative_patterns=negative_patterns or [],
        style_guidelines=style_guidelines or {},
        performance_hints=performance_hints or {},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestGraphMemoryContext:
    """GraphMemoryContext 数据类测试。"""

    def test_default_initialization(self) -> None:
        """测试默认初始化。"""
        ctx = GraphMemoryContext(category="digital")

        assert ctx.category == "digital"
        assert ctx.category_memory is None
        assert ctx.entities == []
        assert ctx.edges == []

    def test_full_initialization(self) -> None:
        """测试完整初始化。"""
        cm = _create_category_memory(1, "digital", summary="类目摘要")
        ctx = GraphMemoryContext(
            category="digital",
            category_memory=cm,
            entities=[{"id": 1, "name": "test"}],
            edges=[{"id": 1, "relationship_type": "related_to"}],
        )

        assert ctx.category_memory is not None
        assert ctx.category_memory.summary == "类目摘要"
        assert len(ctx.entities) == 1
        assert len(ctx.edges) == 1


class TestGraphMemoryService:
    """GraphMemoryService 测试。"""

    @pytest.fixture
    def service(self) -> GraphMemoryService:
        """创建服务实例。"""
        return GraphMemoryService()

    @pytest.fixture
    def mock_session(self) -> MagicMock:
        """创建模拟数据库会话。"""
        session = MagicMock()
        session.execute = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_get_category_memory_not_found(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试类目记忆不存在返回 None。"""
        scalars_mock = MagicMock()
        scalars_mock.first.return_value = None
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.get_category_memory(mock_session, "digital")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_category_memory_found(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试类目记忆存在返回 CategoryMemory 对象。"""
        cm = _create_category_memory(
            1, "digital",
            summary="智能手表类目",
            best_practices=["白色背景"],
            negative_patterns=["避免过曝"],
        )

        scalars_mock = MagicMock()
        scalars_mock.first.return_value = cm
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.get_category_memory(mock_session, "digital")

        assert result is not None
        assert result.summary == "智能手表类目"
        assert result.best_practices == ["白色背景"]
        assert result.negative_patterns == ["避免过曝"]

    @pytest.mark.asyncio
    async def test_list_entities_empty(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试空实体查询。"""
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.list_entities(mock_session, "digital")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_entities_with_results(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试有结果的实体查询。"""
        e1 = _create_entity(1, name="智能手表", entity_type="concept")
        e2 = _create_entity(2, name="Apple", entity_type="brand")

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [e1, e2]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.list_entities(mock_session, "digital")

        assert len(result) == 2
        assert result[0].name == "智能手表"
        assert result[1].name == "Apple"

    @pytest.mark.asyncio
    async def test_list_entities_with_type_filter(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试按实体类型过滤查询。"""
        e1 = _create_entity(1, name="Apple", entity_type="brand")

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [e1]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.list_entities(
            mock_session, "digital", entity_type="brand"
        )

        assert len(result) == 1
        assert result[0].entity_type == "brand"

    @pytest.mark.asyncio
    async def test_list_entities_respects_limit(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试实体查询尊重 limit 参数。"""
        entities = [_create_entity(i, name=f"entity_{i}") for i in range(5)]

        scalars_mock = MagicMock()
        scalars_mock.all.return_value = entities[:3]
        exec_result = MagicMock()
        exec_result.scalars.return_value = scalars_mock
        mock_session.execute.return_value = exec_result

        result = await service.list_entities(mock_session, "digital", limit=3)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_list_edges_empty(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试空边查询。"""
        mock_session.execute.return_value = MagicMock()
        mock_session.execute.return_value.all.return_value = []

        result = await service.list_edges(mock_session, "digital")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_edges_with_results(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试有结果的边查询。"""
        edge = _create_edge(1, 1, 2, "has_attribute", "digital", 0.9, evidence="属性推断")

        row_mock = MagicMock()
        row_mock.__getitem__ = MagicMock(side_effect=[edge, "智能手表", "concept", "长续航", "attribute"])
        row_mock.source_name = "智能手表"
        row_mock.source_type = "concept"
        row_mock.target_name = "长续航"
        row_mock.target_type = "attribute"

        exec_result = MagicMock()
        exec_result.all.return_value = [row_mock]
        mock_session.execute.return_value = exec_result

        result = await service.list_edges(mock_session, "digital")

        assert len(result) == 1
        assert result[0]["relationship_type"] == "has_attribute"
        assert result[0]["weight"] == 0.9
        assert result[0]["evidence"] == "属性推断"
        assert result[0]["source_name"] == "智能手表"
        assert result[0]["source_type"] == "concept"
        assert result[0]["target_name"] == "长续航"
        assert result[0]["target_type"] == "attribute"

    @pytest.mark.asyncio
    async def test_list_edges_with_type_filter(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试按关系类型过滤查询。"""
        edge = _create_edge(1, 1, 2, "has_attribute", "digital", 0.9)

        row_mock = MagicMock()
        row_mock.__getitem__ = MagicMock(side_effect=[edge, "智能手表", "concept", "长续航", "attribute"])
        row_mock.source_name = "智能手表"
        row_mock.source_type = "concept"
        row_mock.target_name = "长续航"
        row_mock.target_type = "attribute"

        exec_result = MagicMock()
        exec_result.all.return_value = [row_mock]
        mock_session.execute.return_value = exec_result

        result = await service.list_edges(
            mock_session, "digital", relationship_type="has_attribute"
        )

        assert len(result) == 1
        assert result[0]["relationship_type"] == "has_attribute"

    @pytest.mark.asyncio
    async def test_build_category_context_empty(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试空上下文构建。"""
        with (
            patch.object(service, "list_entities", new_callable=AsyncMock) as mock_entities,
            patch.object(service, "list_edges", new_callable=AsyncMock) as mock_edges,
            patch.object(service, "get_category_memory", new_callable=AsyncMock) as mock_mem,
        ):
            mock_entities.return_value = []
            mock_edges.return_value = []
            mock_mem.return_value = None

            context = await service.build_category_context(mock_session, "digital")

        assert isinstance(context, GraphMemoryContext)
        assert context.category == "digital"
        assert context.category_memory is None
        assert context.entities == []
        assert context.edges == []

    @pytest.mark.asyncio
    async def test_build_category_context_with_data(
        self, service: GraphMemoryService, mock_session: MagicMock
    ) -> None:
        """测试有数据的上下文构建。"""
        entity = _create_entity(1, name="智能手表", entity_type="concept",
                                description="一款智能手表产品", aliases=["手表", "smartwatch"])
        cm = _create_category_memory(1, "digital", summary="类目摘要",
                                     best_practices=["白色背景"],
                                     negative_patterns=["避免过曝"],
                                     style_guidelines={"风格": "科技简约"},
                                     performance_hints={"表盘": "优先渲染"})

        with (
            patch.object(service, "list_entities", new_callable=AsyncMock) as mock_entities,
            patch.object(service, "list_edges", new_callable=AsyncMock) as mock_edges,
            patch.object(service, "get_category_memory", new_callable=AsyncMock) as mock_mem,
        ):
            mock_entities.return_value = [entity]
            mock_edges.return_value = [{
                "id": 1,
                "source_entity_id": 1,
                "target_entity_id": 2,
                "relationship_type": "has_attribute",
                "weight": 0.9,
                "evidence": "属性推断",
                "source_name": "智能手表",
                "source_type": "concept",
                "target_name": "长续航",
                "target_type": "attribute",
            }]
            mock_mem.return_value = cm

            context = await service.build_category_context(
                mock_session, "digital"
            )

        assert len(context.entities) == 1
        assert context.entities[0]["name"] == "智能手表"
        assert context.entities[0]["description"] == "一款智能手表产品"
        assert context.entities[0]["aliases"] == ["手表", "smartwatch"]
        assert len(context.edges) == 1
        assert context.category_memory is not None
        assert context.category_memory.summary == "类目摘要"


class TestGraphMemoryServiceFormatContext:
    """format_context 方法测试。"""

    @pytest.fixture
    def service(self) -> GraphMemoryService:
        """创建服务实例。"""
        return GraphMemoryService()

    def test_format_empty_context(self, service: GraphMemoryService) -> None:
        """测试空上下文格式化（无类目记忆、无实体、无边）。"""
        ctx = GraphMemoryContext(category="digital")
        formatted = service.format_context(ctx)

        assert formatted == ""

    def test_format_context_with_category_memory(self, service: GraphMemoryService) -> None:
        """测试带类目记忆的上下文格式化。"""
        cm = _create_category_memory(
            1, "digital",
            summary="智能手表类目摘要",
            best_practices=["使用白色背景"],
            negative_patterns=["避免过曝"],
            style_guidelines={"风格": "科技简约"},
            performance_hints={"渲染": "优先渲染表盘"},
        )
        ctx = GraphMemoryContext(
            category="digital",
            category_memory=cm,
        )
        formatted = service.format_context(ctx)

        assert "【类目记忆：digital】" in formatted
        assert "摘要：智能手表类目摘要" in formatted
        assert "最佳实践：" in formatted
        assert "  - 使用白色背景" in formatted
        assert "避坑：" in formatted
        assert "  - 避免过曝" in formatted
        assert "风格指南：" in formatted
        assert "  - 风格: 科技简约" in formatted
        assert "性能提示：" in formatted
        assert "  - 渲染: 优先渲染表盘" in formatted

    def test_format_context_with_entities(self, service: GraphMemoryService) -> None:
        """测试带实体的上下文格式化。"""
        ctx = GraphMemoryContext(
            category="digital",
            entities=[
                {
                    "id": 1,
                    "name": "智能手表",
                    "entity_type": "concept",
                    "description": "可穿戴设备",
                    "aliases": ["手表", "smartwatch"],
                },
            ],
        )
        formatted = service.format_context(ctx)

        assert "【相关实体】" in formatted
        assert "智能手表" in formatted
        assert "concept" in formatted
        assert "可穿戴设备" in formatted
        assert "手表, smartwatch" in formatted

    def test_format_context_with_edges(self, service: GraphMemoryService) -> None:
        """测试带边的上下文格式化。"""
        ctx = GraphMemoryContext(
            category="digital",
            edges=[
                {
                    "id": 1,
                    "source_entity_id": 1,
                    "target_entity_id": 2,
                    "relationship_type": "has_attribute",
                    "weight": 0.85,
                    "evidence": "属性推断",
                    "source_name": "智能手表",
                    "source_type": "concept",
                    "target_name": "长续航",
                    "target_type": "attribute",
                },
            ],
        )
        formatted = service.format_context(ctx)

        assert "【关系线索】" in formatted
        assert "has_attribute" in formatted
        assert "智能手表" in formatted
        assert "长续航" in formatted
        assert "Entity#2" not in formatted
        assert "0.85" in formatted
        assert "依据: 属性推断" in formatted

    def test_format_full_context(self, service: GraphMemoryService) -> None:
        """测试完整上下文格式化。"""
        cm = _create_category_memory(
            1, "digital",
            summary="智能手表类目摘要",
            best_practices=["白色背景"],
            negative_patterns=["避免过曝"],
        )
        ctx = GraphMemoryContext(
            category="digital",
            category_memory=cm,
            entities=[
                {"id": 1, "name": "智能手表", "entity_type": "concept",
                 "description": None, "aliases": []},
            ],
            edges=[
                {"id": 1, "source_entity_id": 1, "target_entity_id": 2,
                 "relationship_type": "has_attribute", "weight": 1.0,
                 "evidence": None, "source_name": "智能手表", "source_type": "concept",
                 "target_name": "长续航", "target_type": "attribute"},
            ],
        )
        formatted = service.format_context(ctx)

        # All three sections present
        assert "【类目记忆：digital】" in formatted
        assert "【相关实体】" in formatted
        assert "【关系线索】" in formatted
        assert "摘要：智能手表类目摘要" in formatted
        assert "最佳实践：" in formatted
        assert "  - 白色背景" in formatted
        assert "避坑：" in formatted
        assert "  - 避免过曝" in formatted


class TestRetrieverGraphMemoryIntegration:
    """retrieve_category_memory_context 集成测试。"""

    def test_retriever_has_method(self) -> None:
        """测试 KnowledgeRetriever 有 retrieve_category_memory_context 方法。"""
        from src.rag.retriever import KnowledgeRetriever
        assert hasattr(KnowledgeRetriever, "retrieve_category_memory_context")

    @pytest.mark.asyncio
    async def test_retrieve_category_memory_context_empty(self) -> None:
        """测试空类目返回空字符串。"""
        from src.rag.retriever import KnowledgeRetriever

        with (
            patch("src.rag.retriever.get_embedding_service") as mock_emb,
            patch("src.rag.retriever.VectorStore"),
        ):
            mock_emb.return_value = MagicMock()
            retriever = KnowledgeRetriever()

            mock_session = MagicMock()
            mock_session.execute = AsyncMock()

            with patch(
                "src.rag.graph_memory.GraphMemoryService"
            ) as mock_service_cls:
                mock_service = MagicMock()
                mock_service.build_category_context = AsyncMock(
                    return_value=GraphMemoryContext(category="digital")
                )
                mock_service_cls.return_value = mock_service

                result = await retriever.retrieve_category_memory_context(
                    mock_session, "digital"
                )

                assert result == ""

    @pytest.mark.asyncio
    async def test_retrieve_category_memory_context_with_data(self) -> None:
        """测试有数据的类目上下文检索返回格式化字符串。"""
        from src.rag.retriever import KnowledgeRetriever

        with (
            patch("src.rag.retriever.get_embedding_service") as mock_emb,
            patch("src.rag.retriever.VectorStore"),
        ):
            mock_emb.return_value = MagicMock()
            retriever = KnowledgeRetriever()

            mock_session = MagicMock()
            mock_session.execute = AsyncMock()

            with patch(
                "src.rag.graph_memory.GraphMemoryService"
            ) as mock_service_cls:
                cm = _create_category_memory(
                    1, "digital",
                    summary="智能手表类目",
                    best_practices=["白色背景"],
                )
                context_with_data = GraphMemoryContext(
                    category="digital",
                    category_memory=cm,
                    entities=[{"id": 1, "name": "test",
                               "entity_type": "concept",
                               "description": None, "aliases": []}],
                )
                mock_service = MagicMock()
                mock_service.build_category_context = AsyncMock(
                    return_value=context_with_data
                )
                mock_service.format_context = MagicMock(
                    return_value="formatted context string"
                )
                mock_service_cls.return_value = mock_service

                result = await retriever.retrieve_category_memory_context(
                    mock_session, "digital"
                )

                assert result == "formatted context string"
                assert isinstance(result, str)
