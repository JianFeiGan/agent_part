"""知识库 Agent 五阶段管道测试。

Description:
    覆盖 KnowledgeAgentWorkflow 的查询分析、策略路由、检索执行、
    RRF 融合与答案生成行为，以及各阶段的降级分支。
    LLM 与检索后端全部以桩替换，不发起真实外部调用。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.vector_store import SearchResult
from src.knowledge.agent_workflow import (
    _ANSWER_FALLBACK,
    INTENT_AGGREGATION,
    INTENT_COMPARISON,
    INTENT_FACT,
    INTENT_REASONING,
    KnowledgeAgentState,
    KnowledgeAgentWorkflow,
)
from src.rag.graph_search import GraphSearchResult

# ==================== 测试桩 ====================


def _vector_hit(
    chunk_id: int,
    content: str,
    score: float,
    title: str = "doc",
) -> SearchResult:
    """构造单条向量检索结果。

    Args:
        chunk_id: 分块 ID。
        content: 分块内容。
        score: 相似度分数。
        title: 来源文档标题。

    Returns:
        检索结果对象。
    """
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=1,
        content=content,
        similarity=score,
        metadata={},
        doc_title=title,
        doc_type="general",
    )


class _RetrieverStub:
    """KnowledgeRetriever 桩：返回预置结果或抛出预置异常，并记录调用。"""

    def __init__(self, outcome: list[SearchResult] | Exception) -> None:
        """初始化桩。

        Args:
            outcome: 预置结果列表，或待抛出的异常。
        """
        self._outcome = outcome
        self.calls: list[dict[str, Any]] = []

    async def retrieve(self, session: Any, query: str, **kwargs: Any) -> Any:
        """执行检索桩。

        Args:
            session: 数据库会话（桩中忽略）。
            query: 查询文本。
            **kwargs: 其余检索参数。

        Returns:
            含 results 字段的简单对象。

        Raises:
            Exception: 预置异常时抛出。
        """
        self.calls.append({"session": session, "query": query, **kwargs})
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return SimpleNamespace(results=self._outcome)


class _GraphStub:
    """GraphSearchService 桩：返回预置结果或抛出预置异常，并记录调用。"""

    def __init__(self, outcome: GraphSearchResult | Exception) -> None:
        """初始化桩。

        Args:
            outcome: 预置检索结果，或待抛出的异常。
        """
        self._outcome = outcome
        self.calls: list[str] = []

    async def search(self, session: Any, query: str, **kwargs: Any) -> Any:
        """执行图谱检索桩。

        Args:
            session: 数据库会话（桩中忽略）。
            query: 查询文本。
            **kwargs: 其余检索参数。

        Returns:
            预置的图谱检索结果。

        Raises:
            Exception: 预置异常时抛出。
        """
        self.calls.append(query)
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


def _scripted_llm(responses: list[str | Exception]) -> Callable[[Any], Any]:
    """构造按调用顺序返回预置响应的伪 LLM。

    Args:
        responses: 预置响应文本或待抛出的异常。

    Returns:
        可注入 chain 的可调用对象。
    """
    queue = list(responses)

    def _call(prompt_value: Any) -> Any:
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(content=item)

    return _call


def _install_llm(monkeypatch: pytest.MonkeyPatch, llm: Callable[[Any], Any] | None) -> None:
    """将 SettingsFallbackLLMProvider 替换为返回 llm 的桩。

    Args:
        monkeypatch: pytest monkeypatch 夹具。
        llm: 伪 LLM；None 表示 LLM 不可用。
    """

    class _Provider:
        def __init__(self, settings: Any = None) -> None:
            self._llm = llm

        def is_available(self) -> bool:
            return llm is not None

        def create_chat_model(self) -> Any:
            return llm

    monkeypatch.setattr("src.clients.openai_compatible_llm.SettingsFallbackLLMProvider", _Provider)


class _Env:
    """工作流测试环境：锁住 graph_rag_enabled 并挂上检索桩。"""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        graph_rag_enabled: bool = False,
        vector_outcome: list[SearchResult] | Exception | None = None,
        graph_outcome: GraphSearchResult | Exception | None = None,
        llm: Callable[[Any], Any] | None = None,
    ) -> None:
        """初始化测试环境。

        Args:
            monkeypatch: pytest monkeypatch 夹具。
            graph_rag_enabled: Graph RAG 开关。
            vector_outcome: 向量检索桩结果/异常，缺省空结果。
            graph_outcome: 图谱检索桩结果/异常，缺省空上下文。
            llm: 伪 LLM，缺省不可用（走规则/摘录降级）。
        """
        self.vector = _RetrieverStub(vector_outcome or [])
        self.graph = _GraphStub(
            graph_outcome
            if graph_outcome is not None
            else GraphSearchResult(answer="", context="", search_mode="local")
        )
        monkeypatch.setattr("src.rag.retriever.KnowledgeRetriever", lambda: self.vector)
        monkeypatch.setattr("src.rag.graph_search.GraphSearchService", lambda: self.graph)
        monkeypatch.setattr(
            "src.knowledge.agent_workflow.get_settings",
            lambda: SimpleNamespace(graph_rag_enabled=graph_rag_enabled),
        )
        _install_llm(monkeypatch, llm)
        self.workflow = KnowledgeAgentWorkflow(
            session=cast(AsyncSession, AsyncMock()),
            tenant_id="t1",
        )

    async def run(self, query: str) -> KnowledgeAgentState:
        """执行工作流。

        Args:
            query: 用户查询。

        Returns:
            工作流状态。
        """
        return await self.workflow.run(query)


# ==================== 1. QueryAnalyzer ====================


class TestQueryAnalyzer:
    """查询分析阶段测试类。"""

    @pytest.mark.asyncio
    async def test_rule_intent_comparison(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """对比类关键词在 LLM 不可用时路由为 COMPARISON。"""
        env = _Env(monkeypatch)

        state = await env.run("智能手表和手环对比哪个好")

        assert state.query_intent == INTENT_COMPARISON
        assert state.entities == []
        assert state.retrieval_strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_rule_intent_aggregation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """统计类关键词在 LLM 不可用时路由为 AGGREGATION。"""
        env = _Env(monkeypatch)

        state = await env.run("知识库总共有多少篇文档")

        assert state.query_intent == INTENT_AGGREGATION

    @pytest.mark.asyncio
    async def test_rule_intent_reasoning(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """推理类关键词在 LLM 不可用时路由为 REASONING。"""
        env = _Env(monkeypatch)

        state = await env.run("为什么需要突出科技感")

        assert state.query_intent == INTENT_REASONING

    @pytest.mark.asyncio
    async def test_rule_intent_fact_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无特征关键词的查询默认按 FACT 处理。"""
        env = _Env(monkeypatch)

        state = await env.run("智能手表的产品参数")

        assert state.query_intent == INTENT_FACT

    @pytest.mark.asyncio
    async def test_llm_analysis_valid_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 返回合法 JSON 时使用其意图与实体。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": ["智能手表", "续航"]}', "答案"])
        env = _Env(
            monkeypatch,
            llm=llm,
            vector_outcome=[_vector_hit(1, "续航持久", 0.9)],
        )

        state = await env.run("智能手表续航")

        assert state.query_intent == INTENT_FACT
        assert state.entities == ["智能手表", "续航"]
        # FACT 且实体 >= 2 → hybrid
        assert state.retrieval_strategy == "hybrid"
        assert state.final_answer == "答案"

    @pytest.mark.asyncio
    async def test_llm_analysis_invalid_intent_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM 返回未知意图时降级为规则分析。"""
        llm = _scripted_llm(['{"intent": "UNKNOWN", "entities": ["a"]}'])
        env = _Env(monkeypatch, llm=llm)

        state = await env.run("智能手表和手环对比")

        assert state.query_intent == INTENT_COMPARISON
        assert state.entities == []

    @pytest.mark.asyncio
    async def test_llm_analysis_malformed_json_falls_back(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM 返回无法解析的 JSON 片段时降级为规则分析。"""
        llm = _scripted_llm(["{not valid json}"])
        env = _Env(monkeypatch, llm=llm)

        state = await env.run("为什么需要防水设计")

        assert state.query_intent == INTENT_REASONING

    @pytest.mark.asyncio
    async def test_llm_analysis_no_json_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 返回纯文本（不含 JSON）时降级为规则分析。"""
        llm = _scripted_llm(["我认为这是一条产品说明。"])
        env = _Env(monkeypatch, llm=llm)

        state = await env.run("智能手表的产品参数")

        assert state.query_intent == INTENT_FACT

    @pytest.mark.asyncio
    async def test_llm_analysis_exception_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 调用抛异常时降级为规则分析。"""
        env = _Env(monkeypatch, llm=_scripted_llm([RuntimeError("llm down")]))

        state = await env.run("有哪些颜色几种")

        assert state.query_intent == INTENT_AGGREGATION


# ==================== 2. StrategyRouter ====================


class TestStrategyRouter:
    """策略路由阶段测试类。"""

    @pytest.mark.asyncio
    async def test_fact_single_entity_routes_vector(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FACT 且实体数 < 2 路由为 vector。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": ["智能手表"]}'])
        env = _Env(monkeypatch, llm=llm)

        state = await env.run("智能手表")

        assert state.retrieval_strategy == "vector"

    @pytest.mark.asyncio
    async def test_fact_multi_entity_routes_hybrid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """FACT 且实体数 >= 2 路由为 hybrid。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": ["a", "b", "c"]}'])
        env = _Env(monkeypatch, llm=llm)

        state = await env.run("a b c")

        assert state.retrieval_strategy == "hybrid"

    @pytest.mark.asyncio
    async def test_reasoning_routes_graph(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """REASONING 路由为 graph。"""
        env = _Env(monkeypatch)

        state = await env.run("如何影响销量")

        assert state.retrieval_strategy == "graph"

    @pytest.mark.asyncio
    async def test_comparison_and_aggregation_route_hybrid(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """COMPARISON / AGGREGATION 均路由为 hybrid。"""
        env = _Env(monkeypatch)

        comparison = await env.run("A 和 B 区别")
        aggregation = await env.run("总共有多少种款式")

        assert comparison.retrieval_strategy == "hybrid"
        assert aggregation.retrieval_strategy == "hybrid"


# ==================== 3. 检索执行 ====================


class TestRetrieval:
    """检索执行阶段测试类。"""

    @pytest.mark.asyncio
    async def test_skipped_without_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无数据库会话时跳过检索并如实记录。"""
        _install_llm(monkeypatch, None)
        monkeypatch.setattr(
            "src.knowledge.agent_workflow.get_settings",
            lambda: SimpleNamespace(graph_rag_enabled=True),
        )
        workflow = KnowledgeAgentWorkflow(session=None, tenant_id="t1")

        state = await workflow.run("智能手表的产品参数")

        retriever_logs = [log for log in state.agent_logs if log["agent"] == "Retriever"]
        assert retriever_logs and retriever_logs[0]["status"] == "skipped"
        assert state.fused_results == []
        assert state.final_answer == _ANSWER_FALLBACK

    @pytest.mark.asyncio
    async def test_vector_strategy_queries_vector_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """vector 策略只走向量检索。"""
        env = _Env(
            monkeypatch,
            vector_outcome=[_vector_hit(1, "内容", 0.8)],
            graph_outcome=GraphSearchResult(
                answer="图谱答案", context="上下文", search_mode="local"
            ),
        )

        state = await env.run("智能手表的产品参数")

        assert state.retrieval_strategy == "vector"
        assert env.vector.calls
        assert env.graph.calls == []
        assert state.vector_results and state.graph_results == []

    @pytest.mark.asyncio
    async def test_graph_strategy_queries_graph_when_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """graph 策略在 Graph RAG 开启时走图谱检索。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            graph_outcome=GraphSearchResult(
                answer="图谱答案", context="相关上下文", search_mode="local"
            ),
        )

        state = await env.run("为什么需要防水设计")

        assert state.retrieval_strategy == "graph"
        assert env.graph.calls
        assert env.vector.calls == []

    @pytest.mark.asyncio
    async def test_graph_strategy_falls_back_to_vector_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """graph 策略在 Graph RAG 关闭时降级为向量检索。"""
        env = _Env(
            monkeypatch, graph_rag_enabled=False, vector_outcome=[_vector_hit(1, "内容", 0.8)]
        )

        state = await env.run("为什么需要防水设计")

        assert state.retrieval_strategy == "graph"
        assert env.vector.calls
        assert env.graph.calls == []
        assert state.vector_results

    @pytest.mark.asyncio
    async def test_hybrid_skips_graph_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """hybrid 策略在 Graph RAG 关闭时只走向量检索。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=False,
            vector_outcome=[_vector_hit(1, "内容", 0.8)],
            graph_outcome=GraphSearchResult(
                answer="图谱答案", context="上下文", search_mode="local"
            ),
        )

        state = await env.run("A 和 B 对比")

        assert state.retrieval_strategy == "hybrid"
        assert env.vector.calls
        assert env.graph.calls == []
        assert state.graph_results == []

    @pytest.mark.asyncio
    async def test_hybrid_retrieves_both_when_graph_enabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """hybrid 策略在 Graph RAG 开启时双路检索。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            vector_outcome=[_vector_hit(1, "向量内容", 0.8)],
            graph_outcome=GraphSearchResult(
                answer="图谱答案", context="图谱上下文", search_mode="hybrid"
            ),
        )

        state = await env.run("A 和 B 对比")

        assert state.retrieval_strategy == "hybrid"
        assert env.vector.calls and env.graph.calls
        assert state.vector_results and state.graph_results

    @pytest.mark.asyncio
    async def test_vector_failure_degrades_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """向量检索异常时按空结果降级。"""
        env = _Env(monkeypatch, vector_outcome=RuntimeError("vector down"))

        state = await env.run("智能手表的产品参数")

        assert state.vector_results == []
        assert state.final_answer == _ANSWER_FALLBACK

    @pytest.mark.asyncio
    async def test_graph_failure_degrades_to_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """图谱检索异常时按空结果降级。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            graph_outcome=RuntimeError("graph down"),
        )

        state = await env.run("为什么需要防水设计")

        assert state.graph_results == []
        assert state.final_answer == _ANSWER_FALLBACK

    @pytest.mark.asyncio
    async def test_graph_placeholder_context_dropped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """图谱返回占位文案（未找到）时视为无结果。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            graph_outcome=GraphSearchResult(
                answer="", context="未找到相关实体", search_mode="local"
            ),
        )

        state = await env.run("为什么需要防水设计")

        assert state.graph_results == []
        assert state.fused_results == []

    @pytest.mark.asyncio
    async def test_graph_answer_and_context_combined(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """图谱结果把 answer 与 context 合并为一条上下文。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            graph_outcome=GraphSearchResult(
                answer="图谱答案", context="关系线索文本", search_mode="local"
            ),
        )

        state = await env.run("为什么需要防水设计")

        assert len(state.graph_results) == 1
        content = state.graph_results[0]["content"]
        assert content.startswith("图谱答案")
        assert "关系线索文本" in content
        assert state.graph_results[0]["id"] == "graph_0"

    @pytest.mark.asyncio
    async def test_run_overrides_session_and_tenant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """run() 的 session/tenant_id 参数覆盖构造值并传给检索器。"""
        env = _Env(monkeypatch, vector_outcome=[_vector_hit(1, "内容", 0.8)])
        override_session = cast(AsyncSession, AsyncMock())

        await env.workflow.run("查询", session=override_session, tenant_id="tenant-x")

        assert env.vector.calls
        assert env.vector.calls[0]["session"] is override_session
        assert env.vector.calls[0]["tenant_id"] == "tenant-x"


# ==================== 4. ResultFuser ====================


class TestResultFuser:
    """RRF 融合阶段测试类。"""

    @pytest.mark.asyncio
    async def test_fusion_sorted_by_rrf_score(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """融合结果按 RRF 分数降序、同 id 只保留一条。"""
        env = _Env(
            monkeypatch,
            graph_rag_enabled=True,
            vector_outcome=[
                _vector_hit(1, "首条", 0.9),
                _vector_hit(2, "次条", 0.8),
            ],
            graph_outcome=GraphSearchResult(answer="", context="图谱内容", search_mode="local"),
        )
        state = await env.run("A 和 B 对比")

        ids = [item["id"] for item in state.fused_results]
        assert len(ids) == len(set(ids))
        assert ids[0] == "1"  # 向量 rank0 分数最高
        scores = [item["score"] for item in state.fused_results]
        assert scores == sorted(scores, reverse=True)

    def test_fusion_accumulates_shared_ids(self) -> None:
        """同 id 双路命中时 RRF 分数累加，排序优于单路次名。

        run() 的向量 id 与图谱 id（graph_0）天然不重叠，
        累加分支只能通过 ResultFuser 的纯函数契约直接验证。
        """
        shared_vector = {"id": "a", "content": "共享", "score": 0.9, "source": "doc"}
        only_vector = {"id": "b", "content": "独有", "score": 0.8, "source": "doc"}
        shared_graph = {"id": "a", "content": "共享", "score": 1.0, "source": "graph"}

        fused = KnowledgeAgentWorkflow._fuse_results([shared_vector, only_vector], [shared_graph])

        assert [item["id"] for item in fused] == ["a", "b"]
        # 1/(60+1) + 1/(60+1) > 1/(60+2)
        assert fused[0]["score"] > fused[1]["score"]

    @pytest.mark.asyncio
    async def test_sources_reflect_fused_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """sources 列表来自融合结果的 id/source/score。"""
        env = _Env(monkeypatch, vector_outcome=[_vector_hit(7, "内容", 0.8, title="手册")])

        state = await env.run("智能手表的产品参数")

        assert state.sources == [
            {"id": "7", "source": "手册", "score": state.fused_results[0]["score"]}
        ]


# ==================== 5. AnswerGenerator ====================


class TestAnswerGenerator:
    """答案生成阶段测试类。"""

    @pytest.mark.asyncio
    async def test_fallback_answer_when_no_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无融合结果时返回固定兜底文案。"""
        env = _Env(monkeypatch)

        state = await env.run("智能手表的产品参数")

        assert state.final_answer == _ANSWER_FALLBACK
        assert state.sources == []

    @pytest.mark.asyncio
    async def test_llm_answer_used_when_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 可用时使用其生成的答案。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": []}', "  基于知识库的回答  "])
        env = _Env(monkeypatch, llm=llm, vector_outcome=[_vector_hit(1, "上下文内容", 0.9)])

        state = await env.run("智能手表的产品参数")

        assert state.final_answer == "基于知识库的回答"

    @pytest.mark.asyncio
    async def test_excerpt_fallback_when_llm_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """答案生成 LLM 失败时降级为 Top-1 摘录。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": []}', RuntimeError("answer down")])
        env = _Env(monkeypatch, llm=llm, vector_outcome=[_vector_hit(1, "最佳片段", 0.9)])

        state = await env.run("智能手表的产品参数")

        assert state.final_answer == "根据知识库内容：\n最佳片段"

    @pytest.mark.asyncio
    async def test_excerpt_fallback_when_llm_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM 返回空答案时降级为 Top-1 摘录。"""
        llm = _scripted_llm(['{"intent": "FACT", "entities": []}', "   "])
        env = _Env(monkeypatch, llm=llm, vector_outcome=[_vector_hit(1, "最佳片段", 0.9)])

        state = await env.run("智能手表的产品参数")

        assert state.final_answer == "根据知识库内容：\n最佳片段"

    @pytest.mark.asyncio
    async def test_excerpt_truncated_to_500_chars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """摘录兜底内容截断到 500 字符。"""
        long_content = "长" * 600
        env = _Env(monkeypatch, vector_outcome=[_vector_hit(1, long_content, 0.9)])

        state = await env.run("智能手表的产品参数")

        assert state.final_answer == f"根据知识库内容：\n{'长' * 500}"


# ==================== LLM 懒加载 ====================


class TestLLMLazyLoad:
    """LLM 懒加载与失败缓存测试类。"""

    @pytest.mark.asyncio
    async def test_llm_unavailable_returns_none_and_caches_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LLM 不可用时返回 None，并缓存失败不再重试。"""
        created = {"count": 0}

        class _Provider:
            def __init__(self, settings: Any = None) -> None:
                created["count"] += 1

            def is_available(self) -> bool:
                return False

            def create_chat_model(self) -> Any:
                raise AssertionError("不应创建模型")

        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.SettingsFallbackLLMProvider", _Provider
        )
        workflow = KnowledgeAgentWorkflow(session=cast(AsyncSession, AsyncMock()), tenant_id="t1")

        first = await workflow._get_llm()
        second = await workflow._get_llm()

        assert first is None
        assert second is None
        assert created["count"] == 1

    @pytest.mark.asyncio
    async def test_llm_created_once_and_cached(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 可用时创建一次并复用缓存实例。"""
        llm = _scripted_llm(["x"])
        created = {"count": 0}

        class _Provider:
            def __init__(self, settings: Any = None) -> None:
                created["count"] += 1

            def is_available(self) -> bool:
                return True

            def create_chat_model(self) -> Any:
                return llm

        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.SettingsFallbackLLMProvider", _Provider
        )
        workflow = KnowledgeAgentWorkflow(session=cast(AsyncSession, AsyncMock()), tenant_id="t1")

        first = await workflow._get_llm()
        second = await workflow._get_llm()

        assert first is llm
        assert second is llm
        assert created["count"] == 1

    @pytest.mark.asyncio
    async def test_llm_init_exception_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """LLM 初始化抛异常时按不可用处理。"""

        class _Provider:
            def __init__(self, settings: Any = None) -> None:
                raise RuntimeError("provider init failed")

        monkeypatch.setattr(
            "src.clients.openai_compatible_llm.SettingsFallbackLLMProvider", _Provider
        )
        workflow = KnowledgeAgentWorkflow(session=cast(AsyncSession, AsyncMock()), tenant_id="t1")

        assert await workflow._get_llm() is None
        assert await workflow._get_llm() is None
