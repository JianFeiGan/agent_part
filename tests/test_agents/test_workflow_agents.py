"""视觉生成工作流 Agent 执行行为测试。

覆盖 OrchestratorAgent 与 RequirementAnalyzerAgent 的输入校验、
LLM 主路径、解析失败回退默认规划/报告，以及异常包装为失败结果。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from langchain_core.prompts import ChatPromptTemplate

from src.agents.orchestrator import OrchestratorAgent
from src.agents.requirement_analyzer import RequirementAnalyzerAgent
from src.graph.state import AgentState, GenerationRequest
from src.models.product import Product, ProductCategory

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _product(**kwargs: Any) -> Product:
    """构造商品。"""
    defaults: dict[str, Any] = {
        "product_id": "prod_001",
        "name": "智能手表",
        "category": ProductCategory.DIGITAL,
        "description": "这是一款用于测试的智能手表商品描述",
    }
    defaults.update(kwargs)
    return Product(**defaults)


def _state(**kwargs: Any) -> AgentState:
    """构造工作流状态。"""
    defaults: dict[str, Any] = {
        "product_info": _product(),
        "generation_request": GenerationRequest(task_id="t1"),
    }
    defaults.update(kwargs)
    return AgentState(**defaults)


def _settings() -> SimpleNamespace:
    """构造 Agent 用到的 Settings 子集。"""
    return SimpleNamespace(
        rag_enabled=False,
        llm_provider="qwen",
        llm_retry_attempts=0,
        llm_retry_initial_backoff=0.01,
    )


def _agent_with_llm(agent: Any, response: Any) -> Any:
    """注入假 LLM 与响应。"""
    agent._llm = MagicMock()  # noqa: SLF001
    agent.invoke_llm = AsyncMock(return_value=response)
    return agent


class TestOrchestrator:
    """OrchestratorAgent.execute。"""

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = OrchestratorAgent(llm=MagicMock(), settings=_settings())

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_success_completes_step(self) -> None:
        """成功时标记步骤完成并给出下一步。"""
        agent = OrchestratorAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(return_value=None)  # noqa: SLF001

        state = _state()
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["next_step"] == "requirement_analysis"
        assert "orchestration" in state.completed_steps
        assert result.data["task_plan"]["estimated_steps"] == 5

    async def test_llm_plan_parsed(self) -> None:
        """LLM 返回 JSON 时采纳其任务规划。"""
        agent = OrchestratorAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(
            return_value=ChatPromptTemplate.from_messages([("human", "{product_info}")])
        )
        _agent_with_llm(
            agent,
            '{"task_type": "image_only", "execution_order": ["a"], "estimated_steps": 1}',
        )

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["task_plan"]["task_type"] == "image_only"

    async def test_unparseable_response_falls_back(self) -> None:
        """LLM 输出无法解析时回退默认规划。"""
        agent = OrchestratorAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(
            return_value=ChatPromptTemplate.from_messages([("human", "{x}")])
        )
        _agent_with_llm(agent, "完全不是 JSON")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["task_plan"]["task_type"] == "image_and_video"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = OrchestratorAgent(llm=MagicMock(), settings=_settings())
        agent._analyze_task = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]  # noqa: SLF001

        result = await agent.execute(_state())

        assert result.success is False
        assert "编排执行失败" in result.error


class TestRequirementAnalyzer:
    """RequirementAnalyzerAgent.execute。"""

    async def test_missing_product_fails(self) -> None:
        """缺商品信息时返回失败结果。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())

        result = await agent.execute(_state(product_info=None))

        assert result.success is False
        assert "缺少商品信息" in result.error

    async def test_default_report_without_prompt(self) -> None:
        """无提示模板时产出默认报告。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(return_value=None)  # noqa: SLF001

        state = _state()
        result = await agent.execute(state)

        assert result.success is True
        assert result.data["requirement_report"]["product_summary"] == "智能手表"
        assert state.requirement_report is not None
        assert "requirement_analysis" in state.completed_steps

    async def test_llm_report_parsed(self) -> None:
        """LLM 返回 JSON 时采纳其分析报告。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(
            return_value=ChatPromptTemplate.from_messages([("human", "{name}")])
        )
        _agent_with_llm(
            agent,
            '{"product_summary": "摘要", "key_features": ["f1"], "selling_points": [],'
            ' "target_audience": ["a"], "style_recommendations": [], "keywords": ["k"]}',
        )

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["requirement_report"]["product_summary"] == "摘要"
        assert result.data["requirement_report"]["key_features"] == ["f1"]

    async def test_unparseable_response_falls_back(self) -> None:
        """LLM 输出无法解析时回退默认报告。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(
            return_value=ChatPromptTemplate.from_messages([("human", "{x}")])
        )
        _agent_with_llm(agent, "不是 JSON")

        result = await agent.execute(_state())

        assert result.success is True
        assert result.data["requirement_report"]["product_summary"] == "智能手表"

    async def test_execute_error_wrapped(self) -> None:
        """执行异常包装为失败结果。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())
        agent._analyze_product = AsyncMock(side_effect=RuntimeError("boom"))  # type: ignore[method-assign]  # noqa: SLF001

        result = await agent.execute(_state())

        assert result.success is False
        assert "需求分析失败" in result.error

    async def test_existing_selling_points_included(self) -> None:
        """已有卖点会进入 LLM 输入。"""
        agent = RequirementAnalyzerAgent(llm=MagicMock(), settings=_settings())
        agent.get_prompt = MagicMock(
            return_value=ChatPromptTemplate.from_messages([("human", "{existing_selling_points}")])
        )
        _agent_with_llm(agent, "不是 JSON")

        product = _product(
            selling_points=[{"title": "续航长", "description": "一次充电使用七天之久"}]
        )
        result = await agent.execute(_state(product_info=product))

        assert result.success is True
        input_vars = agent.invoke_llm.call_args.args[1]
        assert "续航长" in input_vars["existing_selling_points"]
