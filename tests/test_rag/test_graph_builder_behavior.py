"""
GraphBuilderPipeline 行为级测试。

Description:
    只通过公开接口验证 LLM 抽取结果如何落成实体/关系、
    社区发现在依赖缺失时的降级路径，以及 build_from_chunks 的完整编排。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import Select

from src.rag.graph_builder import (
    ExtractedEntity,
    GraphBuilderPipeline,
    get_graph_builder,
)


class FakeLLM:
    """按提示词内容返回预置文本的假 LLM。"""

    def __init__(
        self,
        entities_by_marker: dict[str, str],
        relations_by_marker: dict[str, str],
        summary: str = "社区摘要",
    ) -> None:
        """初始化假 LLM。

        Args:
            entities_by_marker: 文本标记到实体 JSON 的映射。
            relations_by_marker: 文本标记到关系 JSON 的映射。
            summary: 社区摘要返回文本。
        """
        self.entities_by_marker = entities_by_marker
        self.relations_by_marker = relations_by_marker
        self.summary = summary
        self.prompts: list[str] = []

    async def ainvoke(self, prompt: str) -> MagicMock:
        """按提示词类型返回预置内容。

        Args:
            prompt: 提示词。

        Returns:
            带 content 的响应 Mock。
        """
        self.prompts.append(prompt)
        response = MagicMock()
        if "社区摘要" in prompt:
            response.content = self.summary
            return response
        table = self.relations_by_marker if "之间的关系" in prompt else self.entities_by_marker
        response.content = next(
            (payload for marker, payload in table.items() if marker in prompt),
            "[]",
        )
        return response


class FakeRow:
    """select 查询返回的实体行。"""

    def __init__(self, id: int, name: str) -> None:
        """初始化行对象。

        Args:
            id: 实体 ID。
            name: 实体名称。
        """
        self.id = id
        self.name = name


class FakeResult:
    """select 查询结果包装。"""

    def __init__(self, rows: list[FakeRow]) -> None:
        """初始化结果包装。

        Args:
            rows: 行列表。
        """
        self._rows = rows

    def all(self) -> list[FakeRow]:
        """返回全部行。

        Returns:
            行列表。
        """
        return self._rows


class FakeSession:
    """记录语句的假数据库会话。"""

    def __init__(self, entity_rows: list[FakeRow]) -> None:
        """初始化假会话。

        Args:
            entity_rows: 实体查询返回的行。
        """
        self.entity_rows = entity_rows
        self.statements: list[Any] = []
        self.flush_count = 0

    async def execute(self, stmt: Any, *args: Any, **kwargs: Any) -> Any:
        """记录语句，select 返回预置行。

        Args:
            stmt: SQL 语句。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            查询结果或空 Mock。
        """
        self.statements.append(stmt)
        if isinstance(stmt, Select):
            return FakeResult(self.entity_rows)
        return MagicMock()

    async def flush(self) -> None:
        """记录 flush 调用。"""
        self.flush_count += 1

    def tables_written(self) -> list[str]:
        """返回 insert 语句写入的表名列表。

        Returns:
            表名列表。
        """
        return [
            stmt.table.name
            for stmt in self.statements
            if hasattr(stmt, "table") and stmt.table is not None
        ]


def _make_pipeline(llm: Any | None = None) -> GraphBuilderPipeline:
    """构造管道实例，可选注入假 LLM。

    Args:
        llm: 假 LLM 实例，None 则不注入。

    Returns:
        GraphBuilderPipeline 实例。
    """
    pipeline = GraphBuilderPipeline()
    if llm is not None:
        pipeline._llm = llm
    return pipeline


def _entity_payload(*entities: tuple[str, str, str]) -> str:
    """构造实体 JSON 数组文本。

    Args:
        *entities: (name, type, description) 三元组。

    Returns:
        JSON 数组字符串。
    """
    import json

    return json.dumps(
        [{"name": name, "type": etype, "description": desc} for name, etype, desc in entities],
        ensure_ascii=False,
    )


class TestEntityExtractionBehavior:
    """实体抽取的输入输出行为。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("llm_output", "expected"),
        [
            (
                '[{"name": "手表", "type": "产品", "description": "可穿戴"}]',
                [("手表", "产品", "可穿戴")],
            ),
            (
                '```json\n[{"name": "手表", "entity_type": "产品"}]\n```',
                [("手表", "产品", "")],
            ),
            (
                '[{"name": "手表", "type": "产品"}, {"name": "", "type": "产品"}, '
                '{"name": "鞋", "type": ""}, 42]',
                [("手表", "产品", "")],
            ),
            ('{"name": "手表"}', []),
            ("这不是 JSON", []),
            ('[{"name": "手表", "type": "产品"', []),
            ("[]", []),
        ],
    )
    async def test_extract_entities_maps_llm_output(
        self, llm_output: str, expected: list[tuple[str, str, str]]
    ) -> None:
        """LLM 返回不同形态时，抽取结果符合预期。"""
        llm = FakeLLM(entities_by_marker={"任意": llm_output}, relations_by_marker={})
        pipeline = _make_pipeline(llm)

        entities = await pipeline.extract_entities_from_text("任意文本")

        assert [(e.name, e.entity_type, e.description) for e in entities] == expected

    @pytest.mark.asyncio
    async def test_extract_entities_uses_requested_types_in_prompt(self) -> None:
        """自定义实体类型会进入提示词。"""
        llm = FakeLLM(entities_by_marker={"任意": "[]"}, relations_by_marker={})
        pipeline = _make_pipeline(llm)

        await pipeline.extract_entities_from_text("任意文本", entity_types=["品牌", "场景"])

        assert "品牌, 场景" in llm.prompts[0]


class TestRelationExtractionBehavior:
    """关系抽取的输入输出行为。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("llm_output", "expected"),
        [
            (
                '[{"source": "A", "target": "B", "type": "生产", "evidence": "证据"}]',
                [("A", "B", "生产", "证据")],
            ),
            (
                '[{"source_name": "A", "target_name": "B", "relationship_type": "隶属"}]',
                [("A", "B", "隶属", "")],
            ),
            (
                '[{"source": "A", "target": "", "type": "生产"}, {"source": "A", "type": "生产"}, 7]',
                [],
            ),
            ("不是 JSON", []),
        ],
    )
    async def test_extract_relations_maps_llm_output(
        self, llm_output: str, expected: list[tuple[str, str, str, str]]
    ) -> None:
        """LLM 返回不同形态时，关系抽取结果符合预期。"""
        llm = FakeLLM(entities_by_marker={}, relations_by_marker={"任意": llm_output})
        pipeline = _make_pipeline(llm)
        entities = [ExtractedEntity(name="A", entity_type="产品")]

        relations = await pipeline.extract_relations_from_text("任意文本", entities)

        assert [
            (r.source_name, r.target_name, r.relationship_type, r.evidence) for r in relations
        ] == expected

    @pytest.mark.asyncio
    async def test_extract_relations_failure_returns_empty(self) -> None:
        """LLM 调用失败时返回空关系。"""
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM 不可用"))
        pipeline = _make_pipeline(llm)

        relations = await pipeline.extract_relations_from_text(
            "文本", [ExtractedEntity(name="A", entity_type="产品")]
        )

        assert relations == []


class TestCommunityDetectionDegradation:
    """社区发现对 igraph/leidenalg 的依赖降级。"""

    @pytest.fixture
    def pipeline(self) -> GraphBuilderPipeline:
        """创建管道实例。"""
        return GraphBuilderPipeline()

    @pytest.fixture
    def two_components(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """两个连通分量的图数据。"""
        entities = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
            {"id": 3, "name": "C"},
            {"id": 4, "name": "D"},
        ]
        edges = [
            {"source_id": 1, "target_id": 2},
            {"source_id": 3, "target_id": 4},
        ]
        return entities, edges

    def test_leidenalg_available_covers_all_entities(
        self,
        pipeline: GraphBuilderPipeline,
        two_components: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    ) -> None:
        """leidenalg 可用时社区覆盖全部实体。"""
        entities, edges = two_components

        communities = pipeline.detect_communities_leiden(entities, edges, max_communities=10)

        assert communities
        assigned = {eid for comm in communities for eid in comm["entity_ids"]}
        assert assigned == {1, 2, 3, 4}
        assert all(comm["level"] == 0 for comm in communities)
        assert all(comm["community_id"].startswith("comm_") for comm in communities)

    def test_missing_leidenalg_falls_back_to_connected_components(
        self,
        pipeline: GraphBuilderPipeline,
        two_components: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    ) -> None:
        """leidenalg 不可用时按连通分量切分社区。"""
        entities, edges = two_components

        with patch.dict("sys.modules", {"leidenalg": None}):
            communities = pipeline.detect_communities_leiden(entities, edges, max_communities=10)

        assert len(communities) == 2
        sizes = sorted(len(comm["entity_ids"]) for comm in communities)
        assert sizes == [2, 2]

    def test_missing_igraph_falls_back_to_simple_components(
        self,
        pipeline: GraphBuilderPipeline,
        two_components: tuple[list[dict[str, Any]], list[dict[str, Any]]],
    ) -> None:
        """igraph 不可用时用简单连通分量算法。"""
        entities, edges = two_components

        with patch.dict("sys.modules", {"igraph": None, "leidenalg": None}):
            communities = pipeline.detect_communities_leiden(entities, edges, max_communities=10)

        assert len(communities) == 2
        assigned = {eid for comm in communities for eid in comm["entity_ids"]}
        assert assigned == {1, 2, 3, 4}

    def test_missing_igraph_handles_cycles_without_duplicating_entities(
        self, pipeline: GraphBuilderPipeline
    ) -> None:
        """环状图的简单回退不会重复分配实体。"""
        entities = [
            {"id": 1, "name": "A"},
            {"id": 2, "name": "B"},
            {"id": 3, "name": "C"},
        ]
        edges = [
            {"source_id": 1, "target_id": 2},
            {"source_id": 1, "target_id": 3},
            {"source_id": 2, "target_id": 3},
        ]

        with patch.dict("sys.modules", {"igraph": None, "leidenalg": None}):
            communities = pipeline.detect_communities_leiden(entities, edges, max_communities=10)

        assert len(communities) == 1
        assert sorted(communities[0]["entity_ids"]) == [1, 2, 3]

    def test_missing_igraph_respects_max_communities(self, pipeline: GraphBuilderPipeline) -> None:
        """简单回退同样遵守 max_communities 上限。"""
        entities = [{"id": i, "name": f"E{i}"} for i in range(5)]

        with patch.dict("sys.modules", {"igraph": None, "leidenalg": None}):
            communities = pipeline.detect_communities_leiden(entities, [], max_communities=2)

        assert len(communities) == 2

    def test_empty_entities_yield_no_communities(self, pipeline: GraphBuilderPipeline) -> None:
        """空实体列表返回空社区。"""
        assert pipeline.detect_communities_leiden([], []) == []


class TestCommunitySummary:
    """社区摘要生成行为。"""

    @pytest.mark.asyncio
    async def test_empty_entities_yield_empty_summary(self) -> None:
        """无实体时摘要为空字符串。"""
        pipeline = _make_pipeline()
        assert await pipeline.generate_community_summary([], []) == ""

    @pytest.mark.asyncio
    async def test_summary_uses_llm_output(self) -> None:
        """摘要取 LLM 返回文本并去除首尾空白。"""
        llm = FakeLLM(entities_by_marker={}, relations_by_marker={}, summary="  摘要内容  ")
        pipeline = _make_pipeline(llm)

        summary = await pipeline.generate_community_summary(["A", "B"], ["A --> B"])

        assert summary == "摘要内容"
        assert "A, B" in llm.prompts[0]
        assert "A --> B" in llm.prompts[0]

    @pytest.mark.asyncio
    async def test_missing_relations_use_placeholder(self) -> None:
        """无关系信息时提示词使用占位说明。"""
        llm = FakeLLM(entities_by_marker={}, relations_by_marker={}, summary="摘要")
        pipeline = _make_pipeline(llm)

        await pipeline.generate_community_summary(["A"], [])

        assert "无关系信息" in llm.prompts[0]

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_entity_list(self) -> None:
        """LLM 失败时回退为实体罗列摘要。"""
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("不可用"))
        pipeline = _make_pipeline(llm)

        summary = await pipeline.generate_community_summary(["A", "B"], [])

        assert summary == "包含实体: A, B"


class TestBuildFromChunks:
    """build_from_chunks 完整编排行为。"""

    @pytest.mark.asyncio
    async def test_empty_chunks_yield_zero_counts(self) -> None:
        """无有效分块时统计全为 0。"""
        session = FakeSession(entity_rows=[])
        pipeline = _make_pipeline(FakeLLM({}, {}))

        result = await pipeline.build_from_chunks(session, [], category="digital")

        assert result == {
            "entity_count": 0,
            "relation_count": 0,
            "community_count": 0,
            "category": "digital",
        }
        assert session.flush_count == 2

    @pytest.mark.asyncio
    async def test_blank_chunk_content_is_skipped(self) -> None:
        """空内容分块不触发抽取。"""
        llm = FakeLLM({}, {})
        session = FakeSession(entity_rows=[])
        pipeline = _make_pipeline(llm)

        result = await pipeline.build_from_chunks(
            session, [{"content": ""}, {"no_content": True}], category="digital"
        )

        assert result["entity_count"] == 0
        assert llm.prompts == []

    @pytest.mark.asyncio
    async def test_pipeline_dedups_entities_and_filters_invalid_relations(self) -> None:
        """实体按 name:type 去重，自环与未知实体的关系被丢弃。"""
        llm = FakeLLM(
            entities_by_marker={
                "文本一": _entity_payload(
                    ("手表", "产品", "可穿戴设备"),
                    ("Acme", "品牌", "品牌方"),
                ),
                "文本二": _entity_payload(
                    ("手表", "产品", "重复实体"),
                    ("防水", "技术", "防水能力"),
                ),
            },
            relations_by_marker={
                "文本一": '[{"source": "手表", "target": "Acme", "type": "生产", "evidence": "e1"}]',
                "文本二": (
                    '[{"source": "手表", "target": "手表", "type": "自环", "evidence": "e2"},'
                    ' {"source": "手表", "target": "幽灵", "type": "未知", "evidence": "e3"}]'
                ),
            },
        )
        session = FakeSession(
            entity_rows=[FakeRow(1, "手表"), FakeRow(2, "Acme"), FakeRow(3, "防水")]
        )
        pipeline = _make_pipeline(llm)

        result = await pipeline.build_from_chunks(
            session,
            [{"content": "文本一"}, {"content": "文本二"}],
            category="digital",
            tenant_id="t1",
        )

        assert result["entity_count"] == 3
        assert result["relation_count"] == 1
        assert result["category"] == "digital"

        written = session.tables_written()
        assert written.count("graph_rag_entities") == 3
        assert written.count("graph_rag_edges") == 1

    @pytest.mark.asyncio
    async def test_communities_are_summarized_and_persisted(self) -> None:
        """社区被摘要并写入 community_summaries 表。"""
        llm = FakeLLM(
            entities_by_marker={
                "文本": _entity_payload(("A", "产品", ""), ("B", "品牌", "")),
            },
            relations_by_marker={
                "文本": '[{"source": "A", "target": "B", "type": "生产", "evidence": "e"}]',
            },
            summary="A 由 B 生产",
        )
        session = FakeSession(entity_rows=[FakeRow(1, "A"), FakeRow(2, "B")])
        pipeline = _make_pipeline(llm)

        result = await pipeline.build_from_chunks(
            session, [{"content": "文本"}], category="digital", tenant_id="t1"
        )

        assert result["community_count"] >= 1
        written = session.tables_written()
        assert written.count("community_summaries") == result["community_count"]

    @pytest.mark.asyncio
    async def test_identical_relations_are_each_counted(self) -> None:
        """管道不做关系去重，重复关系逐条计数落库。"""
        llm = FakeLLM(
            entities_by_marker={
                "文本": _entity_payload(("A", "产品", ""), ("B", "品牌", "")),
            },
            relations_by_marker={
                "文本": (
                    '[{"source": "A", "target": "B", "type": "生产", "evidence": "e"},'
                    ' {"source": "A", "target": "B", "type": "生产", "evidence": "e"}]'
                ),
            },
        )
        session = FakeSession(entity_rows=[FakeRow(1, "A"), FakeRow(2, "B")])
        pipeline = _make_pipeline(llm)

        result = await pipeline.build_from_chunks(
            session, [{"content": "文本"}], category="digital"
        )

        # 两条关系都会持久化（管道按关系列表逐条落库），计数反映实际插入数
        assert result["relation_count"] == 2
        assert session.tables_written().count("graph_rag_edges") == 2

    @pytest.mark.asyncio
    async def test_self_relation_is_skipped(self) -> None:
        """source 与 target 相同的关系不落库。"""
        llm = FakeLLM(
            entities_by_marker={"文本": _entity_payload(("A", "产品", ""))},
            relations_by_marker={
                "文本": '[{"source": "A", "target": "A", "type": "自环", "evidence": ""}]',
            },
        )
        session = FakeSession(entity_rows=[FakeRow(1, "A")])
        pipeline = _make_pipeline(llm)

        result = await pipeline.build_from_chunks(
            session, [{"content": "文本"}], category="digital"
        )

        assert result["relation_count"] == 0
        assert "graph_rag_edges" not in session.tables_written()


class TestLLMProviderSelection:
    """LLM 懒加载在不同 provider 配置下的行为。"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("provider", "has_dashscope_key", "expect_qwen"),
        [
            ("qwen", False, True),
            ("dashscope", True, False),
            ("dashscope", False, True),
            ("unknown", False, True),
        ],
    )
    async def test_provider_config_selects_llm_client(
        self, provider: str, has_dashscope_key: bool, expect_qwen: bool
    ) -> None:
        """不同 provider 配置下抽取仍能拿到 LLM 并完成解析。"""
        settings = MagicMock()
        settings.llm_provider = provider
        settings.llm_model = "model-x"
        settings.effective_dashscope_api_key = "key" if has_dashscope_key else ""

        fake_llm = FakeLLM(
            entities_by_marker={"任意": _entity_payload(("手表", "产品", ""))},
            relations_by_marker={},
        )
        fake_qwen_mod = MagicMock()
        fake_qwen_mod.get_qwen_llm = MagicMock(return_value=fake_llm)
        fake_chat_models = MagicMock()
        fake_chat_models.ChatTongyi = MagicMock(return_value=fake_llm)

        pipeline = GraphBuilderPipeline()
        pipeline.settings = settings

        with patch.dict(
            "sys.modules",
            {
                "src.clients.qwen_llm_client": fake_qwen_mod,
                "langchain_community.chat_models": fake_chat_models,
            },
        ):
            entities = await pipeline.extract_entities_from_text("任意文本")

        assert [e.name for e in entities] == ["手表"]
        if expect_qwen:
            fake_qwen_mod.get_qwen_llm.assert_called_once()
            fake_chat_models.ChatTongyi.assert_not_called()
        else:
            fake_chat_models.ChatTongyi.assert_called_once()
            fake_qwen_mod.get_qwen_llm.assert_not_called()


class TestGetGraphBuilder:
    """get_graph_builder 单例行为。"""

    def test_returns_singleton(self) -> None:
        """重复调用返回同一实例。"""
        import src.rag.graph_builder as graph_builder_module

        original = graph_builder_module._graph_builder
        try:
            graph_builder_module._graph_builder = None
            first = get_graph_builder()
            second = get_graph_builder()
            assert first is second
        finally:
            graph_builder_module._graph_builder = original
