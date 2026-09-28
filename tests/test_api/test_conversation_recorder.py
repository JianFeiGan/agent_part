"""AI 会话记录服务行为测试。

覆盖费用计算、内容截断、token 提取的三种来源、上下文管理器的成败分支，
以及数据库不可用时的静默降级。不触碰真实数据库。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.service.conversation_recorder import (
    ConversationRecorder,
    _calculate_cost,
    record_conversation,
)

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


class _SessionCtx:
    """可 async with 的会话替身。"""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _patch_db(monkeypatch: pytest.MonkeyPatch, session: AsyncMock) -> None:
    """注入 get_db_session 替身。"""
    monkeypatch.setattr(
        "src.api.service.conversation_recorder.get_db_session",
        lambda: _SessionCtx(session),
    )


def _patch_repo(monkeypatch: pytest.MonkeyPatch, created: Any) -> MagicMock:
    """注入 BaseRepository 替身，返回实例以便断言。"""
    instance = MagicMock()
    instance.create = AsyncMock(return_value=created)
    monkeypatch.setattr(
        "src.api.service.conversation_recorder.BaseRepository",
        lambda *_a, **_k: instance,
    )
    return instance


class TestCalculateCost:
    """费用计算。"""

    def test_known_model_uses_pricing_table(self) -> None:
        """定价表内模型按表计费。"""
        usd, cny = _calculate_cost("qwen-plus", 1000, 1000)
        assert usd == pytest.approx(0.0008 + 0.002)
        assert cny == pytest.approx(usd * 7.2)

    def test_unknown_model_uses_default_pricing(self) -> None:
        """定价表外模型回落到默认价。"""
        usd, _cny = _calculate_cost("unknown-model", 1000, 1000)
        assert usd == pytest.approx(0.001 + 0.002)

    def test_zero_tokens_cost_zero(self) -> None:
        """零 token 费用为零。"""
        assert _calculate_cost("qwen-plus", 0, 0) == (0.0, 0.0)


class TestRecordConversation:
    """record_conversation 行为。"""

    async def test_persists_with_computed_cost(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """写入记录并带上计算出的费用与 token 总数。"""
        session = AsyncMock()
        _patch_db(monkeypatch, session)
        instance = _patch_repo(monkeypatch, created=MagicMock())

        await record_conversation(
            tenant_id="tenant-a",
            model_name="qwen-plus",
            input_tokens=1000,
            output_tokens=1000,
        )

        kwargs = instance.create.await_args.kwargs
        assert kwargs["tenant_id"] == "tenant-a"
        assert kwargs["total_tokens"] == 2000
        assert kwargs["cost_usd"] > 0
        assert kwargs["cost_cny"] > 0

    async def test_truncates_long_content(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """超长输入/输出内容被截断，避免撑爆数据库。"""
        session = AsyncMock()
        _patch_db(monkeypatch, session)
        instance = _patch_repo(monkeypatch, created=MagicMock())

        await record_conversation(
            tenant_id="tenant-a",
            model_name="qwen-plus",
            input_content="x" * 6000,
            output_content="y" * 6000,
        )

        kwargs = instance.create.await_args.kwargs
        assert kwargs["input_content"].endswith("...(已截断)")
        assert len(kwargs["input_content"]) < 6000
        assert kwargs["output_content"].endswith("...(已截断)")

    async def test_db_failure_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """数据库异常时返回 None，不向上抛。"""

        class _BrokenCtx:
            async def __aenter__(self) -> Any:
                raise RuntimeError("db down")

            async def __aexit__(self, *exc: Any) -> None:
                return None

        monkeypatch.setattr("src.api.service.conversation_recorder.get_db_session", _BrokenCtx)

        assert await record_conversation(tenant_id="t", model_name="m") is None


class TestConversationRecorder:
    """ConversationRecorder 上下文管理器。"""

    async def test_success_records_status_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """正常退出时以 success 状态落库。"""
        recorded: dict[str, Any] = {}

        async def _capture(**kwargs: Any) -> Any:
            recorded.update(kwargs)
            return MagicMock()

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _capture)

        async with ConversationRecorder(
            tenant_id="tenant-a", model_name="qwen-plus", input_content="in"
        ) as recorder:
            recorder.set_response(SimpleNamespace(content="out"))

        assert recorded["status"] == "success"
        assert recorded["output_content"] == "out"

    async def test_exception_marks_failed_and_reraises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """块内异常记为 failed，且异常继续向上抛。"""
        recorded: dict[str, Any] = {}

        async def _capture(**kwargs: Any) -> Any:
            recorded.update(kwargs)
            return MagicMock()

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _capture)

        with pytest.raises(RuntimeError, match="llm boom"):
            async with ConversationRecorder(tenant_id="t", model_name="m"):
                raise RuntimeError("llm boom")

        assert recorded["status"] == "failed"
        assert "llm boom" in recorded["error_message"]

    async def test_recorder_failure_does_not_mask_original_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """记录写入失败不影响原始异常传播。"""

        async def _boom(**_kwargs: Any) -> Any:
            raise RuntimeError("record failed")

        monkeypatch.setattr("src.api.service.conversation_recorder.record_conversation", _boom)

        with pytest.raises(ValueError, match="original"):
            async with ConversationRecorder(tenant_id="t", model_name="m"):
                raise ValueError("original")

    def test_set_response_reads_usage_metadata_dict(self) -> None:
        """usage_metadata 为 dict 时按 input/output_tokens 提取。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(
            SimpleNamespace(
                content="hi",
                usage_metadata={"input_tokens": 11, "output_tokens": 22},
            )
        )

        assert recorder._input_tokens == 11  # noqa: SLF001
        assert recorder._output_tokens == 22  # noqa: SLF001

    def test_set_response_reads_usage_metadata_object(self) -> None:
        """usage_metadata 为对象时用 getattr 提取。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(
            SimpleNamespace(
                content="hi",
                usage_metadata=SimpleNamespace(input_tokens=5, output_tokens=6),
            )
        )

        assert recorder._input_tokens == 5  # noqa: SLF001
        assert recorder._output_tokens == 6  # noqa: SLF001

    def test_set_response_falls_back_to_response_metadata(self) -> None:
        """无 usage_metadata 时从 response_metadata.token_usage 提取。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(
            SimpleNamespace(
                content="hi",
                response_metadata={"token_usage": {"prompt_tokens": 3, "completion_tokens": 4}},
            )
        )

        assert recorder._input_tokens == 3  # noqa: SLF001
        assert recorder._output_tokens == 4  # noqa: SLF001

    def test_set_response_reads_dashscope_usage(self) -> None:
        """DashScope 风格 response_metadata.usage 也可提取。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(
            SimpleNamespace(
                content="hi",
                response_metadata={"usage": {"prompt_tokens": 7, "completion_tokens": 8}},
            )
        )

        assert recorder._input_tokens == 7  # noqa: SLF001
        assert recorder._output_tokens == 8  # noqa: SLF001

    def test_set_response_list_content_stringified(self) -> None:
        """多模态 list 内容被转成字符串。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(SimpleNamespace(content=["a", "b"], usage_metadata=None))

        assert isinstance(recorder._output_content, str)  # noqa: SLF001
        assert "a" in recorder._output_content  # noqa: SLF001

    def test_set_response_without_metadata_leaves_tokens_zero(self) -> None:
        """无任何 token 元数据时保持 0。"""
        recorder = ConversationRecorder(tenant_id="t", model_name="m")
        recorder.set_response(SimpleNamespace(content="plain"))

        assert recorder._input_tokens == 0  # noqa: SLF001
        assert recorder._output_tokens == 0  # noqa: SLF001
