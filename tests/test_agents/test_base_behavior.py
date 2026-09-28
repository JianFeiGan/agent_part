"""BaseAgent 行为测试。

覆盖 LLM 懒加载、类目记忆检索的各降级分支、上下文截断、
重试调用与 invoke_llm 的 Trace 记录。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import (
    CATEGORY_MEMORY_MAX_CHARS,
    AgentRole,
    BaseAgent,
)

# conftest 会把 BaseAgent._create_llm 打成 ImportError，这里捕获真实实现。
_REAL_CREATE_LLM = BaseAgent._create_llm

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


class _Agent(BaseAgent[Any]):
    """最小可实例化的 Agent 实现。"""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(role=AgentRole.CREATIVE_PLANNER, **kwargs)

    async def execute(self, state: Any) -> Any:  # pragma: no cover - 抽象占位
        return state


def _settings(**kwargs: Any) -> SimpleNamespace:
    """构造 BaseAgent 用到的 Settings 子集。"""
    defaults: dict[str, Any] = {
        "rag_enabled": True,
        "llm_provider": "qwen",
        "llm_retry_attempts": 1,
        "llm_retry_initial_backoff": 0.01,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestLLMLazyInit:
    """llm 属性的懒加载。"""

    def test_uses_injected_llm(self) -> None:
        """构造时传入的 llm 直接复用，不触发 _create_llm。"""
        llm = MagicMock()
        agent = _Agent(llm=llm, settings=_settings())

        assert agent.llm is llm

    def test_creates_when_missing(self) -> None:
        """未注入时调用 _create_llm 并缓存结果。"""
        created = MagicMock()
        agent = _Agent(settings=_settings())
        agent._create_llm = MagicMock(return_value=created)  # type: ignore[method-assign]  # noqa: SLF001

        assert agent.llm is created
        assert agent.llm is created
        agent._create_llm.assert_called_once()  # noqa: SLF001

    def test_create_llm_raises_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无任何 API Key 时抛 ImportError，指引配置。"""
        monkeypatch.setattr(BaseAgent, "_create_llm", _REAL_CREATE_LLM)
        agent = _Agent(
            settings=SimpleNamespace(dashscope_api_key="", sensenova_api_key="", llm_model="m")
        )
        with pytest.raises(ImportError, match="未配置任何 LLM Provider"):
            agent._create_llm()  # noqa: SLF001

    def test_create_llm_uses_settings_provider(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """配置了 Key 时产出真实 ChatModel。"""
        monkeypatch.setattr(BaseAgent, "_create_llm", _REAL_CREATE_LLM)
        agent = _Agent(
            settings=SimpleNamespace(
                dashscope_api_key="sk", sensenova_api_key="", llm_model="qwen-plus"
            )
        )

        model = agent._create_llm()  # noqa: SLF001

        assert model.model_name == "qwen-plus"


class TestRagFlag:
    """has_rag / retriever。"""

    def test_no_retriever_means_no_rag(self) -> None:
        """无检索器时无 RAG 能力。"""
        agent = _Agent(settings=_settings())
        assert agent.retriever is None
        assert agent.has_rag() is False

    def test_rag_disabled_means_no_rag(self) -> None:
        """配置关闭 RAG 时即使有检索器也不启用。"""
        agent = _Agent(retriever=MagicMock(), settings=_settings(rag_enabled=False))
        assert agent.has_rag() is False

    def test_retriever_and_enabled_means_rag(self) -> None:
        """检索器存在且 RAG 开启时启用。"""
        retriever = MagicMock()
        agent = _Agent(retriever=retriever, settings=_settings())
        assert agent.retriever is retriever
        assert agent.has_rag() is True


class TestTruncateContext:
    """上下文截断。"""

    def test_short_context_unchanged(self) -> None:
        """未超长原样返回。"""
        assert BaseAgent._truncate_context("abc", max_chars=10) == "abc"

    def test_long_context_truncated_with_ellipsis(self) -> None:
        """超长截断并以省略号结尾。"""
        text = "x" * (CATEGORY_MEMORY_MAX_CHARS + 50)
        result = BaseAgent._truncate_context(text)

        assert len(result) == CATEGORY_MEMORY_MAX_CHARS + 3
        assert result.endswith("...")


class TestCategoryMemory:
    """_retrieve_category_memory_context 的降级链。"""

    async def test_no_rag_returns_empty(self) -> None:
        """无 RAG 能力直接返回空串。"""
        agent = _Agent(settings=_settings(rag_enabled=False), retriever=MagicMock())

        assert await agent._retrieve_category_memory_context(MagicMock(), "digital") == ""  # noqa: SLF001

    async def test_no_session_returns_empty(self) -> None:
        """无数据库会话返回空串。"""
        agent = _Agent(settings=_settings(), retriever=MagicMock())

        assert await agent._retrieve_category_memory_context(None, "digital") == ""  # noqa: SLF001

    async def test_empty_category_returns_empty(self) -> None:
        """类目为空返回空串。"""
        agent = _Agent(settings=_settings(), retriever=MagicMock())

        assert await agent._retrieve_category_memory_context(MagicMock(), "") == ""  # noqa: SLF001

    async def test_retriever_without_method_returns_empty(self) -> None:
        """检索器不支持领域方法时返回空串。"""

        class _Plain:
            pass

        agent = _Agent(settings=_settings(), retriever=_Plain())

        assert await agent._retrieve_category_memory_context(MagicMock(), "digital") == ""  # noqa: SLF001

    async def test_fetch_error_degrades_to_empty(self) -> None:
        """检索异常按无记忆降级，不向上抛。"""

        class _Broken:
            async def retrieve_category_memory_context(self, *_a: Any, **_k: Any) -> str:
                raise RuntimeError("retriever down")

        agent = _Agent(settings=_settings(), retriever=_Broken(), tenant_id="tenant-1")

        assert await agent._retrieve_category_memory_context(MagicMock(), "digital") == ""  # noqa: SLF001

    async def test_non_string_result_degrades_to_empty(self) -> None:
        """返回非字符串视为无记忆。"""

        class _Weird:
            async def retrieve_category_memory_context(self, *_a: Any, **_k: Any) -> Any:
                return ["not", "a", "string"]

        agent = _Agent(settings=_settings(), retriever=_Weird())

        assert await agent._retrieve_category_memory_context(MagicMock(), "digital") == ""  # noqa: SLF001

    async def test_returns_truncated_context(self) -> None:
        """成功路径返回截断后的记忆文本。"""

        class _OK:
            async def retrieve_category_memory_context(
                self, _session: Any, category: str, *, tenant_id: str
            ) -> str:
                return f"记忆-{category}-{tenant_id}"

        agent = _Agent(settings=_settings(), retriever=_OK(), tenant_id="tenant-1")

        result = await agent._retrieve_category_memory_context(MagicMock(), "digital")  # noqa: SLF001

        assert result == "记忆-digital-tenant-1"

    async def test_truncates_long_memory(self) -> None:
        """超长记忆被截断。"""

        class _Long:
            async def retrieve_category_memory_context(self, *_a: Any, **_k: Any) -> str:
                return "m" * (CATEGORY_MEMORY_MAX_CHARS + 10)

        agent = _Agent(settings=_settings(), retriever=_Long())

        result = await agent._retrieve_category_memory_context(MagicMock(), "digital")  # noqa: SLF001

        assert result.endswith("...")
        assert len(result) == CATEGORY_MEMORY_MAX_CHARS + 3


class TestInvokeWithRetry:
    """_ainvoke_with_retry 的重试语义。"""

    async def test_succeeds_first_try(self) -> None:
        """首次成功直接返回。"""
        agent = _Agent(settings=_settings(llm_retry_attempts=2))
        chain = MagicMock()
        chain.ainvoke = AsyncMock(return_value="ok")

        assert await agent._ainvoke_with_retry(chain, {"a": 1}) == "ok"  # noqa: SLF001

    async def test_retries_then_succeeds(self) -> None:
        """瞬态失败后重试成功。"""
        agent = _Agent(settings=_settings(llm_retry_attempts=2, llm_retry_initial_backoff=0.01))
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=[RuntimeError("flaky"), "ok"])

        assert await agent._ainvoke_with_retry(chain, {}) == "ok"  # noqa: SLF001
        assert chain.ainvoke.await_count == 2

    async def test_exhausted_retries_raise(self) -> None:
        """重试耗尽后抛出原始异常。"""
        agent = _Agent(settings=_settings(llm_retry_attempts=1, llm_retry_initial_backoff=0.01))
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=RuntimeError("always down"))

        with pytest.raises(RuntimeError, match="always down"):
            await agent._ainvoke_with_retry(chain, {})  # noqa: SLF001

        assert chain.ainvoke.await_count == 2

    async def test_zero_attempts_calls_once(self) -> None:
        """attempts=0 时只调用一次。"""
        agent = _Agent(settings=_settings(llm_retry_attempts=0))
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError):
            await agent._ainvoke_with_retry(chain, {})  # noqa: SLF001

        assert chain.ainvoke.await_count == 1


class TestInvokeLLM:
    """invoke_llm 的 Trace 记录。"""

    async def test_records_trace_and_returns_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """调用成功时记录 Trace 并返回文本内容。"""
        recorded: dict[str, Any] = {}

        async def _capture(**kwargs: Any) -> Any:
            recorded.update(kwargs)
            return MagicMock()

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _capture)

        response = SimpleNamespace(
            content="生成结果",
            usage_metadata={"input_tokens": 10, "output_tokens": 20},
        )
        agent = _Agent(settings=_settings(), llm=MagicMock(model_name="qwen-plus"))
        agent._ainvoke_with_retry = AsyncMock(return_value=response)  # type: ignore[method-assign]  # noqa: SLF001

        prompt = ChatPromptTemplate.from_messages([("human", "{topic}")])
        result = await agent.invoke_llm(prompt, {"topic": "科技感"})

        assert result == "生成结果"
        trace = agent._last_trace  # noqa: SLF001
        assert trace is not None
        assert trace["input_tokens"] == 10
        assert trace["output_tokens"] == 20
        assert trace["total_tokens"] == 30
        assert trace["model_name"] == "qwen-plus"
        assert trace["provider"] == "qwen"

    async def test_non_string_response_stringified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """无 content 属性的响应转字符串返回。"""

        async def _noop(**_kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _noop)

        agent = _Agent(settings=_settings(), llm=MagicMock())
        agent._ainvoke_with_retry = AsyncMock(return_value=12345)  # type: ignore[method-assign]  # noqa: SLF001

        prompt = ChatPromptTemplate.from_messages([("human", "{t}")])
        assert await agent.invoke_llm(prompt, {"t": "x"}) == "12345"

    async def test_prompt_format_failure_falls_back_to_str(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """模板无法 format 时以字符串形式记录模板。"""

        async def _noop(**_kwargs: Any) -> Any:
            return MagicMock()

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _noop)

        agent = _Agent(settings=_settings(), llm=MagicMock())
        agent._ainvoke_with_retry = AsyncMock(  # type: ignore[method-assign]  # noqa: SLF001
            return_value=SimpleNamespace(content="ok", usage_metadata=None)
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{missing}")])
        result = await agent.invoke_llm(prompt, {"other": "v"})

        assert result == "ok"
        assert agent._last_trace is not None  # noqa: SLF001

    def test_repr_shows_role(self) -> None:
        """__repr__ 输出类名与角色。"""
        agent = _Agent(settings=_settings())
        assert "CREATIVE_PLANNER" in repr(agent) or "creative_planner" in repr(agent)


class TestRegisterPrompt:
    """提示模板注册。"""

    def test_register_and_retrieve(self) -> None:
        """注册的模板可按名称取回。"""
        agent = _Agent(settings=_settings())
        prompt = ChatPromptTemplate.from_messages([("human", "{x}")])

        agent.register_prompt("p1", prompt)

        assert agent._prompts["p1"] is prompt  # noqa: SLF001
