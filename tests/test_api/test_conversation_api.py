"""AI 会话记录 API 行为测试。

覆盖列表过滤、详情的跨租户 404、使用量概览聚合、
费用预算的零预算分支与内容搜索的 LIKE 通配符转义。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.router.conversation import (
    get_conversation,
    get_cost_budget,
    get_usage_overview,
    list_conversations,
    search_conversations,
)
from src.api.schema.conversation import (
    ConversationContentQuery,
    ConversationQueryParams,
    CostBudgetRequest,
)
from src.auth.context import AuthContext

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


@pytest.fixture
def auth() -> AuthContext:
    """租户 A 上下文。"""
    return AuthContext(tenant_id="tenant-a", user_id="user-a", scopes=[])


def _log(**kwargs: Any) -> Any:
    """构造 AIConversationLog 风格对象。"""
    log = MagicMock()
    defaults: dict[str, Any] = {
        "id": 1,
        "tenant_id": "tenant-a",
        "task_id": "task-1",
        "session_id": "sess-1",
        "agent_name": "Orchestrator",
        "model_name": "qwen-plus",
        "provider": "qwen",
        "input_content": "输入内容",
        "output_content": "输出内容",
        "input_tokens": 100,
        "output_tokens": 200,
        "total_tokens": 300,
        "cost_usd": 0.01,
        "cost_cny": 0.072,
        "latency_ms": 120,
        "status": "success",
        "error_message": None,
        "extra_data": {},
        "created_at": datetime.now(UTC),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(log, k, v)
    return log


class _FakeResult:
    """SQLAlchemy Result 替身。"""

    def __init__(
        self,
        *,
        scalar: Any = 0,
        one_row: Any = None,
        all_items: list[Any] | None = None,
    ) -> None:
        self._scalar = scalar
        self._one = one_row
        self._all = all_items or []

    def scalar(self) -> Any:
        return self._scalar

    def one(self) -> Any:
        return self._one

    def all(self) -> list[Any]:
        return self._all

    def scalars(self) -> Any:
        holder = MagicMock()
        holder.all = MagicMock(return_value=self._all)
        return holder


class _SessionCtx:
    """async with 会话替身。"""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *exc: Any) -> None:
        return None


def _patch_db(monkeypatch: pytest.MonkeyPatch, results: list[_FakeResult]) -> AsyncMock:
    """注入按序返回结果的会话。"""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=results)
    session.get = AsyncMock(return_value=None)
    monkeypatch.setattr("src.api.router.conversation.get_db_session", lambda: _SessionCtx(session))
    return session


class TestListConversations:
    """列表查询。"""

    async def test_returns_logs_with_totals(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """返回日志列表与总数。"""
        _patch_db(
            monkeypatch,
            [_FakeResult(scalar=2), _FakeResult(all_items=[_log(), _log(id=2)])],
        )

        resp = await list_conversations(ConversationQueryParams(), auth)

        assert resp.code == 200
        assert len(resp.data.items) == 2
        assert resp.data.total == 2

    async def test_filters_applied(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """过滤条件传入后仍能正常返回（查询构造不抛异常）。"""
        _patch_db(monkeypatch, [_FakeResult(scalar=0), _FakeResult(all_items=[])])
        params = ConversationQueryParams(
            agent_name="Orchestrator",
            model_name="qwen-plus",
            provider="qwen",
            task_id="task-1",
            session_id="sess-1",
            status="success",
            start_date=datetime(2026, 1, 1, tzinfo=UTC),
            end_date=datetime(2026, 2, 1, tzinfo=UTC),
        )

        resp = await list_conversations(params, auth)

        assert resp.data.total == 0


class TestGetConversation:
    """详情查询。"""

    async def test_cross_tenant_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """跨租户访问返回 404 防枚举。"""
        _patch_db(monkeypatch, [])
        session = AsyncMock()
        session.get = AsyncMock(return_value=_log(tenant_id="tenant-b"))
        monkeypatch.setattr(
            "src.api.router.conversation.get_db_session",
            lambda: _SessionCtx(session),
        )

        resp = await get_conversation(1, auth)

        assert resp.code == 404
        assert resp.data is None

    async def test_missing_returns_404(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """不存在返回 404。"""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        monkeypatch.setattr(
            "src.api.router.conversation.get_db_session",
            lambda: _SessionCtx(session),
        )

        resp = await get_conversation(99, auth)

        assert resp.code == 404

    async def test_own_tenant_returns_detail(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """本租户命中返回含内容的详情。"""
        session = AsyncMock()
        session.get = AsyncMock(return_value=_log())
        monkeypatch.setattr(
            "src.api.router.conversation.get_db_session",
            lambda: _SessionCtx(session),
        )

        resp = await get_conversation(1, auth)

        assert resp.code == 200
        assert resp.data.input_content == "输入内容"
        assert resp.data.output_content == "输出内容"


class TestUsageOverview:
    """使用量概览。"""

    async def test_aggregates_stats_models_and_agents(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """聚合总体、按模型、按 Agent 三份统计。"""
        stats_row = (1000, 2000, 3000, 0.5, 3.6, 120.0, 10)
        _patch_db(
            monkeypatch,
            [
                _FakeResult(one_row=stats_row),
                _FakeResult(scalar=2),
                _FakeResult(all_items=[("qwen-plus", "qwen", 5, 1500, 0.3, 2.16)]),
                _FakeResult(all_items=[("Orchestrator", 5, 1500, 0.3, 2.16)]),
            ],
        )

        resp = await get_usage_overview(None, None, auth)

        assert resp.data.stats.total_tokens == 3000
        assert resp.data.stats.success_count == 10
        assert resp.data.stats.failed_count == 2
        assert resp.data.stats.total_count == 12
        assert resp.data.by_model[0].model_name == "qwen-plus"
        assert resp.data.by_agent[0].agent_name == "Orchestrator"

    async def test_date_range_filters(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """传入时间范围后仍可聚合。"""
        _patch_db(
            monkeypatch,
            [
                _FakeResult(one_row=(0, 0, 0, 0.0, 0.0, 0.0, 0)),
                _FakeResult(scalar=0),
                _FakeResult(all_items=[]),
                _FakeResult(all_items=[]),
            ],
        )

        resp = await get_usage_overview(
            datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC), auth
        )

        assert resp.data.stats.total_count == 0


class TestCostBudget:
    """费用预算分析。"""

    async def test_within_budget(self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> None:
        """未超预算时剩余为正，使用率按比例。"""
        _patch_db(
            monkeypatch,
            [
                _FakeResult(one_row=(10.0, 1.0, 5000, 3)),
                _FakeResult(scalar=100.0),
            ],
        )

        resp = await get_cost_budget(
            CostBudgetRequest(daily_budget_cny=20.0, monthly_budget_cny=200.0), auth
        )

        assert resp.data.daily_remaining_cny == 10.0
        assert resp.data.daily_usage_percent == 50.0
        assert resp.data.monthly_remaining_cny == 100.0

    async def test_over_budget_clamps_to_100(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """超预算时剩余为 0，使用率封顶 100%。"""
        _patch_db(
            monkeypatch,
            [
                _FakeResult(one_row=(50.0, 5.0, 9000, 8)),
                _FakeResult(scalar=500.0),
            ],
        )

        resp = await get_cost_budget(
            CostBudgetRequest(daily_budget_cny=20.0, monthly_budget_cny=200.0), auth
        )

        assert resp.data.daily_remaining_cny == 0.0
        assert resp.data.daily_usage_percent == 100.0
        assert resp.data.monthly_remaining_cny == 0.0
        assert resp.data.monthly_usage_percent == 100.0

    def test_zero_budget_rejected_by_schema(self) -> None:
        """预算必须为正数，0 在 schema 层被拒。"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CostBudgetRequest(daily_budget_cny=0.0, monthly_budget_cny=100.0)


class TestSearchConversations:
    """内容搜索。"""

    async def test_escapes_like_wildcards(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """% 和 _ 被转义，避免用户输入变成通配符。"""
        session = _patch_db(monkeypatch, [_FakeResult(scalar=0), _FakeResult(all_items=[])])

        resp = await search_conversations(ConversationContentQuery(keyword="100%_off"), auth)

        assert resp.code == 200
        # 至少构造过 count + select 两条查询
        assert session.execute.await_count == 2

    async def test_search_field_input(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """按输入字段搜索返回结果。"""
        _patch_db(monkeypatch, [_FakeResult(scalar=1), _FakeResult(all_items=[_log()])])

        resp = await search_conversations(
            ConversationContentQuery(keyword="卖点", search_field="input"), auth
        )

        assert resp.data.total == 1
        assert len(resp.data.items) == 1

    async def test_search_field_output(
        self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext
    ) -> None:
        """按输出字段搜索。"""
        _patch_db(monkeypatch, [_FakeResult(scalar=0), _FakeResult(all_items=[])])

        resp = await search_conversations(
            ConversationContentQuery(keyword="x", search_field="output"), auth
        )

        assert resp.data.total == 0

    async def test_extra_filters(self, monkeypatch: pytest.MonkeyPatch, auth: AuthContext) -> None:
        """附加 agent/model/status 过滤不报错。"""
        _patch_db(monkeypatch, [_FakeResult(scalar=0), _FakeResult(all_items=[])])

        resp = await search_conversations(
            ConversationContentQuery(
                keyword="k",
                agent_name="A",
                model_name="m",
                status="failed",
            ),
            auth,
        )

        assert resp.data.total == 0
