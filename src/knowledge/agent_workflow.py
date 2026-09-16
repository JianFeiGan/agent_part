"""知识库 Agent 工作流。

Description:
    五阶段管道：QueryAnalyzer（意图/实体分析）→ StrategyRouter（策略路由）
    → 检索执行（vector / graph / hybrid）→ ResultFuser（RRF 融合）
    → AnswerGenerator（答案生成）。
    各阶段失败时降级：LLM 不可用时用规则分析意图、
    用图谱直出答案或 Top-1 摘录兜底最终回答。
@author ganjianfei
@version 2.0.0
2026-09-16
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# 查询意图
INTENT_FACT = "FACT"
INTENT_REASONING = "REASONING"
INTENT_COMPARISON = "COMPARISON"
INTENT_AGGREGATION = "AGGREGATION"

# 检索策略
STRATEGY_VECTOR = "vector"
STRATEGY_GRAPH = "graph"
STRATEGY_HYBRID = "hybrid"

# RRF 融合常数
_RRF_K = 60

_ANSWER_FALLBACK = "未检索到与问题相关的知识库内容。"


@dataclass
class KnowledgeAgentState:
    """知识库 Agent 工作流状态。

    Attributes:
        query: 用户查询。
        query_intent: 查询意图 (FACT/REASONING/COMPARISON/AGGREGATION)。
        entities: 查询中提取的实体。
        retrieval_strategy: 路由的检索策略 (vector/graph/hybrid)。
        vector_results: 向量检索结果。
        graph_results: 图谱检索结果。
        fused_results: RRF 融合后的结果。
        final_answer: 最终回答。
        sources: 来源列表。
        agent_logs: Agent 执行日志。
    """

    query: str = ""
    query_intent: str = INTENT_FACT
    entities: list[str] = field(default_factory=list)
    retrieval_strategy: str = STRATEGY_VECTOR
    vector_results: list[dict[str, Any]] = field(default_factory=list)
    graph_results: list[dict[str, Any]] = field(default_factory=list)
    fused_results: list[dict[str, Any]] = field(default_factory=list)
    final_answer: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    agent_logs: list[dict[str, Any]] = field(default_factory=list)


class KnowledgeAgentWorkflow:
    """知识库 Agent 工作流。

    组合现有检索服务（KnowledgeRetriever / GraphSearchService）与 LLM，
    执行「查询分析 → 策略路由 → 检索 → 融合 → 答案生成」五阶段管道。

    Example:
        >>> workflow = KnowledgeAgentWorkflow(session=session, tenant_id="t1")
        >>> state = await workflow.run("智能手表有哪些卖点？")
        >>> print(state.final_answer)
    """

    def __init__(
        self,
        session: AsyncSession | None = None,
        tenant_id: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        """初始化工作流。

        Args:
            session: 数据库会话（可选，缺省时检索阶段跳过并如实记录）。
            tenant_id: 租户 ID（可选）。
            settings: 应用配置，默认从 get_settings() 读取。
        """
        self._session = session
        self._tenant_id = tenant_id
        self._settings = settings or get_settings()
        self._llm: Any = None
        self._llm_failed = False

    async def run(
        self,
        query: str,
        session: AsyncSession | None = None,
        tenant_id: str | None = None,
    ) -> KnowledgeAgentState:
        """执行知识库查询工作流。

        Args:
            query: 用户查询。
            session: 可选，覆盖构造时的数据库会话。
            tenant_id: 可选，覆盖构造时的租户 ID。

        Returns:
            工作流状态。
        """
        if session is not None:
            self._session = session
        if tenant_id is not None:
            self._tenant_id = tenant_id

        state = KnowledgeAgentState(query=query)

        # 1. QueryAnalyzer：意图分类 + 实体提取
        state.query_intent, state.entities = await self._analyze_query(query)
        state.agent_logs.append(
            {
                "agent": "QueryAnalyzer",
                "status": "completed",
                "summary": f"意图={state.query_intent}, 实体数={len(state.entities)}",
            }
        )

        # 2. StrategyRouter：按规则路由检索策略
        state.retrieval_strategy = self._route_strategy(state.query_intent, state.entities)
        state.agent_logs.append(
            {
                "agent": "StrategyRouter",
                "status": "completed",
                "summary": f"策略={state.retrieval_strategy}",
            }
        )

        # 3. 检索执行
        await self._retrieve(state)

        # 4. ResultFuser：RRF 融合
        state.fused_results = self._fuse_results(state.vector_results, state.graph_results)
        state.agent_logs.append(
            {
                "agent": "ResultFuser",
                "status": "completed",
                "summary": f"融合结果数={len(state.fused_results)}",
            }
        )

        # 5. AnswerGenerator：生成最终答案
        state.final_answer = await self._generate_answer(state)
        state.sources = [
            {"id": r["id"], "source": r.get("source"), "score": r.get("score", 0.0)}
            for r in state.fused_results
        ]
        state.agent_logs.append(
            {
                "agent": "AnswerGenerator",
                "status": "completed",
                "summary": f"答案长度={len(state.final_answer)}",
            }
        )

        return state

    # ==================== 1. QueryAnalyzer ====================

    async def _analyze_query(self, query: str) -> tuple[str, list[str]]:
        """分析查询意图并提取实体（LLM 优先，规则兜底）。

        Args:
            query: 用户查询。

        Returns:
            (意图, 实体列表) 元组。
        """
        llm = await self._get_llm()
        if llm is not None:
            try:
                from langchain_core.prompts import ChatPromptTemplate

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "你是查询分析器。分析用户查询的意图并提取关键实体。"
                            '仅返回 JSON：{{"intent": "FACT|REASONING|COMPARISON|AGGREGATION", '
                            '"entities": ["实体1", "实体2"]}}。'
                            "意图定义：FACT=事实查询；REASONING=原因/方法推理；"
                            "COMPARISON=对比；AGGREGATION=统计汇总。不要输出其他内容。",
                        ),
                        ("human", "{query}"),
                    ]
                )
                chain = prompt | llm
                response = await chain.ainvoke({"query": query})
                text = response.content if hasattr(response, "content") else str(response)
                match = re.search(r"\{.*\}", str(text), re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    intent = str(data.get("intent", "")).upper()
                    entities = [str(e) for e in data.get("entities", []) if e]
                    if intent in {
                        INTENT_FACT,
                        INTENT_REASONING,
                        INTENT_COMPARISON,
                        INTENT_AGGREGATION,
                    }:
                        return intent, entities
            except Exception as e:
                logger.warning(f"查询分析 LLM 调用失败，降级为规则分析: {e}")

        return self._analyze_query_by_rules(query), []

    @staticmethod
    def _analyze_query_by_rules(query: str) -> str:
        """基于关键词规则的意图分类兜底。

        Args:
            query: 用户查询。

        Returns:
            意图标识。
        """
        if re.search(r"对比|比较|区别|vs|VS|哪个好", query):
            return INTENT_COMPARISON
        if re.search(r"所有|全部|总共|多少|数量|统计|几种|哪些", query):
            return INTENT_AGGREGATION
        if re.search(r"为什么|原因|如何|怎么|怎样|影响|原理", query):
            return INTENT_REASONING
        return INTENT_FACT

    # ==================== 2. StrategyRouter ====================

    @staticmethod
    def _route_strategy(intent: str, entities: list[str]) -> str:
        """按规则路由检索策略。

        规则：FACT 且实体 >= 2 → hybrid；FACT → vector；
        REASONING → graph；COMPARISON/AGGREGATION → hybrid。

        Args:
            intent: 查询意图。
            entities: 提取的实体列表。

        Returns:
            检索策略标识。
        """
        if intent == INTENT_FACT:
            return STRATEGY_HYBRID if len(entities) >= 2 else STRATEGY_VECTOR
        if intent == INTENT_REASONING:
            return STRATEGY_GRAPH
        return STRATEGY_HYBRID

    # ==================== 3. 检索执行 ====================

    async def _retrieve(self, state: KnowledgeAgentState) -> None:
        """按策略执行向量/图谱检索。

        Args:
            state: 工作流状态（就地更新 vector_results / graph_results）。
        """
        if self._session is None:
            state.agent_logs.append(
                {
                    "agent": "Retriever",
                    "status": "skipped",
                    "summary": "无数据库会话，跳过检索",
                }
            )
            return

        strategy = state.retrieval_strategy
        if strategy in (STRATEGY_VECTOR, STRATEGY_HYBRID):
            state.vector_results = await self._vector_search(state.query)
        if strategy in (STRATEGY_GRAPH, STRATEGY_HYBRID):
            state.graph_results = await self._graph_search(state.query)
        state.agent_logs.append(
            {
                "agent": "Retriever",
                "status": "completed",
                "summary": (
                    f"vector={len(state.vector_results)}, graph={len(state.graph_results)}"
                ),
            }
        )

    async def _vector_search(self, query: str) -> list[dict[str, Any]]:
        """向量检索（经 KnowledgeRetriever，含高级 RAG 管道）。

        Args:
            query: 用户查询。

        Returns:
            归一化结果列表。
        """
        try:
            from src.rag.retriever import KnowledgeRetriever

            retriever = KnowledgeRetriever()
            result = await retriever.retrieve(
                self._session,  # type: ignore[arg-type]
                query,
                tenant_id=self._tenant_id or "",
            )
            return [
                {
                    "id": str(r.chunk_id),
                    "content": r.content,
                    "score": r.similarity,
                    "source": r.doc_title or "vector",
                }
                for r in result.results
            ]
        except Exception as e:
            logger.warning(f"向量检索失败，按空结果降级: {e}")
            return []

    async def _graph_search(self, query: str) -> list[dict[str, Any]]:
        """图谱检索（经 GraphSearchService）。

        Args:
            query: 用户查询。

        Returns:
            归一化结果列表（单条上下文记录）。
        """
        try:
            from src.rag.graph_search import GraphSearchService

            service = GraphSearchService()
            result = await service.search(
                self._session,  # type: ignore[arg-type]
                query,
                category="",
                tenant_id=self._tenant_id,
            )
            content = result.context or ""
            if result.answer:
                content = f"{result.answer}\n\n{content}"
            if not content.strip() or content.strip() in {"未找到相关实体", "未找到相关社区摘要"}:
                return []
            return [
                {
                    "id": "graph_0",
                    "content": content,
                    "score": 1.0,
                    "source": "graph",
                }
            ]
        except Exception as e:
            logger.warning(f"图谱检索失败，按空结果降级: {e}")
            return []

    # ==================== 4. ResultFuser ====================

    @staticmethod
    def _fuse_results(
        vector_results: list[dict[str, Any]],
        graph_results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """RRF 融合多路检索结果。

        score(d) = Σ 1 / (k + rank_i(d))，按融合分降序。

        Args:
            vector_results: 向量检索结果（按相似度降序）。
            graph_results: 图谱检索结果。

        Returns:
            融合后的结果列表。
        """
        fused: dict[str, dict[str, Any]] = {}
        for results in (vector_results, graph_results):
            for rank, item in enumerate(results):
                key = item["id"]
                if key not in fused:
                    fused[key] = {**item, "score": 0.0}
                fused[key]["score"] += 1.0 / (_RRF_K + rank + 1)
        return sorted(fused.values(), key=lambda r: r["score"], reverse=True)

    # ==================== 5. AnswerGenerator ====================

    async def _generate_answer(self, state: KnowledgeAgentState) -> str:
        """基于融合上下文生成答案（LLM 优先，摘录兜底）。

        Args:
            state: 工作流状态。

        Returns:
            最终答案文本。
        """
        if not state.fused_results:
            return _ANSWER_FALLBACK

        context = "\n\n".join(r["content"] for r in state.fused_results[:5])
        llm = await self._get_llm()
        if llm is not None:
            try:
                from langchain_core.prompts import ChatPromptTemplate

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "你是知识库问答助手。仅基于给定上下文回答问题，"
                            "上下文不足时如实说明，不要编造。",
                        ),
                        ("human", "上下文：\n{context}\n\n问题：{query}"),
                    ]
                )
                chain = prompt | llm
                response = await chain.ainvoke({"context": context, "query": state.query})
                answer = response.content if hasattr(response, "content") else str(response)
                answer = str(answer).strip()
                if answer:
                    return answer
            except Exception as e:
                logger.warning(f"答案生成 LLM 调用失败，降级为摘录: {e}")

        # 兜底：Top-1 摘录
        top = state.fused_results[0]
        return f"根据知识库内容：\n{top['content'][:500]}"

    # ==================== LLM ====================

    async def _get_llm(self) -> Any | None:
        """懒加载 LLM（不可用时返回 None，不抛异常）。"""
        if self._llm is not None:
            return self._llm
        if self._llm_failed:
            return None

        try:
            from src.clients.openai_compatible_llm import SettingsFallbackLLMProvider

            provider = SettingsFallbackLLMProvider(settings=self._settings)
            if provider.is_available():
                self._llm = provider.create_chat_model()
                return self._llm
        except Exception as e:
            logger.warning(f"LLM 初始化失败: {e}")

        self._llm_failed = True
        return None
