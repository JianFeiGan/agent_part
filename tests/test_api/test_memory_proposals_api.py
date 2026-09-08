"""
记忆提案 API 测试。

Description:
    测试 /api/v1/memory-proposals 下的 distill、列表、详情、approve、reject 接口。
    handler 直接调用 + FakeDBSession 注入（session 现为显式参数，
    无需字符串 patch get_db）。
    注意：租户过滤在 SQL 层完成，fake 模拟 DB 视角——跨租户场景返回
    None（与"不存在"不可区分，防枚举）。
@author ganjianfei
@version 1.1.0
2026-09-08
"""

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest
from fastapi import HTTPException

from src.auth.context import AuthContext

# ============================================================================
# Auth fixtures
# ============================================================================


@pytest.fixture
def auth_a() -> AuthContext:
    """租户 A，拥有 memory:* scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-a",
        scopes=["memory:read", "memory:write"],
    )


@pytest.fixture
def auth_b() -> AuthContext:
    """租户 B，拥有 memory:* scope。"""
    return AuthContext(
        tenant_id="tenant-b",
        user_id="user-b",
        scopes=["memory:read", "memory:write"],
    )


@pytest.fixture
def auth_readonly() -> AuthContext:
    """只读 scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-ro",
        scopes=["memory:read"],
    )


@pytest.fixture
def auth_no_scope() -> AuthContext:
    """无 memory scope。"""
    return AuthContext(
        tenant_id="tenant-a",
        user_id="user-none",
        scopes=[],
    )


# ============================================================================
# Fake DB Session
# ============================================================================


class FakeDBSession:
    """模拟 AsyncSession。"""

    def __init__(
        self,
        *,
        scalars_return: list[Any] | None = None,
        scalars_first_return: Any = None,
        add_side_effect: Any = None,
        commit_side_effect: Any = None,
    ) -> None:
        self.added: list[Any] = []
        self._scalars_return = scalars_return or []
        self._scalars_first = scalars_first_return
        self._add_side_effect = add_side_effect
        self._commit_side_effect = commit_side_effect
        self.committed = False
        self.rolled_back = False
        self.refreshed: list[Any] = []

    def add(self, obj: Any) -> None:
        if self._add_side_effect is not None:
            if isinstance(self._add_side_effect, Exception):
                raise self._add_side_effect
            self._add_side_effect(obj)
        self.added.append(obj)

    async def commit(self) -> None:
        if self._commit_side_effect is not None:
            if isinstance(self._commit_side_effect, Exception):
                raise self._commit_side_effect
            self._commit_side_effect()
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, obj: Any) -> None:
        self.refreshed.append(obj)
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 1
        if not hasattr(obj, "created_at") or obj.created_at is None:
            obj.created_at = datetime.now(UTC)
        if not hasattr(obj, "updated_at") or obj.updated_at is None:
            obj.updated_at = datetime.now(UTC)

    async def execute(self, _stmt: Any) -> Any:
        return _FakeResult(
            scalars_all=self._scalars_return,
            scalars_first=self._scalars_first,
        )

    async def flush(self) -> None:
        pass


class _FakeResult:
    def __init__(
        self,
        scalars_all: list[Any] | None = None,
        scalars_first: Any = None,
    ) -> None:
        self._scalars_all = scalars_all or []
        self._scalars_first = scalars_first

    def scalars(self) -> "_FakeScalars":
        return _FakeScalars(self._scalars_all, self._scalars_first)


class _FakeScalars:
    def __init__(self, all_items: list[Any], first_item: Any = None) -> None:
        self._all = all_items
        self._first = first_item

    def all(self) -> list[Any]:
        return self._all

    def first(self) -> Any:
        return self._first


# ============================================================================
# Helpers
# ============================================================================


def _make_proposal(
    id: int = 1,
    tenant_id: str = "tenant-a",
    category: str = "digital",
    status: str = "pending",
    **kwargs: Any,
) -> Any:
    """创建一个类似 CategoryMemoryProposalPO 的假对象。"""
    obj = mock.MagicMock()
    obj.id = id
    obj.tenant_id = tenant_id
    obj.category = category
    obj.summary = kwargs.get("summary", "测试摘要")
    obj.best_practices = kwargs.get("best_practices", [])
    obj.negative_patterns = kwargs.get("negative_patterns", [])
    obj.style_guidelines = kwargs.get("style_guidelines", {})
    obj.performance_hints = kwargs.get("performance_hints", {})
    obj.source_type = kwargs.get("source_type", "task_completion")
    obj.source_ref = kwargs.get("source_ref", "task-001")
    obj.status = status
    obj.confidence = kwargs.get("confidence", 0.5)
    obj.reviewed_by = kwargs.get("reviewed_by")
    obj.review_reason = kwargs.get("review_reason")
    obj.created_at = kwargs.get("created_at", datetime.now(UTC))
    obj.updated_at = kwargs.get("updated_at", datetime.now(UTC))
    obj.reviewed_at = kwargs.get("reviewed_at")
    return obj


def _make_memory(
    id: int = 1,
    tenant_id: str = "tenant-a",
    category: str = "digital",
    **kwargs: Any,
) -> Any:
    """创建一个类似 CategoryMemory 的假对象。"""
    obj = mock.MagicMock()
    obj.id = id
    obj.tenant_id = tenant_id
    obj.category = category
    obj.summary = kwargs.get("summary", "已有摘要")
    obj.best_practices = kwargs.get("best_practices", ["已有实践1"])
    obj.negative_patterns = kwargs.get("negative_patterns", ["已有问题1"])
    obj.style_guidelines = kwargs.get("style_guidelines", {"旧风格": "简约"})
    obj.performance_hints = kwargs.get("performance_hints", {"旧提示": "value"})
    obj.extra_data = kwargs.get("extra_data", {})
    obj.created_at = kwargs.get("created_at", datetime.now(UTC))
    obj.updated_at = kwargs.get("updated_at", datetime.now(UTC))
    return obj


# ============================================================================
# List Proposals Tests
# ============================================================================


class TestListProposals:
    """测试获取提案列表。"""

    def test_list_proposals_filters_by_tenant_and_status(self, auth_a: AuthContext) -> None:
        """列表应按租户和状态过滤。"""
        from src.api.router.memory_proposals import list_proposals

        p1 = _make_proposal(id=1, status="pending")
        p2 = _make_proposal(id=2, status="pending")
        session = FakeDBSession(scalars_return=[p1, p2])

        async def _run() -> None:
            result = await list_proposals(auth=auth_a, session=session, status_filter="pending")
            assert result.code == 200
            assert len(result.data) == 2

        asyncio.run(_run())

    def test_list_proposals_empty(self, auth_a: AuthContext) -> None:
        """空列表。"""
        from src.api.router.memory_proposals import list_proposals

        session = FakeDBSession(scalars_return=[])

        async def _run() -> None:
            result = await list_proposals(auth=auth_a, session=session)
            assert result.code == 200
            assert result.data == []

        asyncio.run(_run())

    def test_list_proposals_requires_scope(self, auth_no_scope: AuthContext) -> None:
        """无 scope 应返回 403。"""
        from src.api.router.memory_proposals import list_proposals

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await list_proposals(auth=auth_no_scope, session=FakeDBSession())
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ============================================================================
# Get Proposal Tests
# ============================================================================


class TestGetProposal:
    """测试获取提案详情。"""

    def test_get_proposal_own_tenant(self, auth_a: AuthContext) -> None:
        """本租户可获取详情。"""
        from src.api.router.memory_proposals import get_proposal

        p = _make_proposal(id=1, tenant_id="tenant-a")
        session = FakeDBSession(scalars_first_return=p)

        async def _run() -> None:
            result = await get_proposal(proposal_id=1, auth=auth_a, session=session)
            assert result.code == 200
            assert result.data is not None

        asyncio.run(_run())

    def test_get_proposal_cross_tenant_returns_404(self, auth_a: AuthContext) -> None:
        """跨租户访问返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.memory_proposals import get_proposal

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_proposal(proposal_id=1, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_get_proposal_not_found(self, auth_a: AuthContext) -> None:
        """不存在的提案返回 404。"""
        from src.api.router.memory_proposals import get_proposal

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await get_proposal(proposal_id=999, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())


# ============================================================================
# Approve Tests
# ============================================================================


class TestApproveProposal:
    """测试审批通过。"""

    def test_approve_creates_category_memory_when_not_exists(self, auth_a: AuthContext) -> None:
        """不存在对应 CategoryMemory 时创建新记录。"""
        from src.api.router.memory_proposals import approve_proposal

        proposal = _make_proposal(
            id=1,
            status="pending",
            best_practices=["新实践"],
            negative_patterns=["新问题"],
        )
        # 第一个 execute 返回 proposal，第二个（查询 CategoryMemory）返回 None
        session = FakeDBSession()

        call_count = 0

        async def _execute(_stmt: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult(scalars_first=proposal)
            # second call: query CategoryMemory -> None
            return _FakeResult(scalars_first=None)

        session.execute = _execute  # type: ignore[method-assign]

        async def _run() -> None:
            result = await approve_proposal(proposal_id=1, auth=auth_a, session=session)
            assert result.code == 200
            assert "审批通过" in result.message
            # proposal status should be "applied"
            assert proposal.status == "applied"
            assert proposal.reviewed_by == "user-a"
            assert proposal.reviewed_at is not None
            # CategoryMemory 被创建
            assert len(session.added) == 1
            assert session.added[0].tenant_id == "tenant-a"

        asyncio.run(_run())

    def test_approve_merges_existing_category_memory(self, auth_a: AuthContext) -> None:
        """已有 CategoryMemory 时 merge 字段。"""
        from src.api.router.memory_proposals import approve_proposal

        proposal = _make_proposal(
            id=1,
            status="pending",
            best_practices=["新实践"],
            negative_patterns=["新问题"],
            style_guidelines={"新风格": "科技感"},
            performance_hints={"新提示": "value"},
        )
        existing = _make_memory(
            id=10,
            best_practices=["已有实践1"],
            negative_patterns=["已有问题1"],
            style_guidelines={"旧风格": "简约"},
            performance_hints={"旧提示": "old"},
        )

        call_count = 0

        async def _execute(_stmt: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult(scalars_first=proposal)
            return _FakeResult(scalars_first=existing)

        session = FakeDBSession()
        session.execute = _execute  # type: ignore[method-assign]

        async def _run() -> None:
            result = await approve_proposal(proposal_id=1, auth=auth_a, session=session)
            assert result.code == 200
            # Check merge: best_practices should have both
            assert "已有实践1" in existing.best_practices
            assert "新实践" in existing.best_practices
            # Check merge: negative_patterns should have both
            assert "已有问题1" in existing.negative_patterns
            assert "新问题" in existing.negative_patterns
            # Check merge: style_guidelines merged, proposal wins
            assert existing.style_guidelines["旧风格"] == "简约"
            assert existing.style_guidelines["新风格"] == "科技感"

        asyncio.run(_run())

    def test_approve_marks_status_applied(self, auth_a: AuthContext) -> None:
        """审批通过后 status 应为 applied。"""
        from src.api.router.memory_proposals import approve_proposal

        proposal = _make_proposal(id=1, status="pending")
        session = FakeDBSession()
        call_count = 0

        async def _execute(_stmt: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _FakeResult(scalars_first=proposal)
            return _FakeResult(scalars_first=None)

        session.execute = _execute  # type: ignore[method-assign]

        async def _run() -> None:
            await approve_proposal(proposal_id=1, auth=auth_a, session=session)
            assert proposal.status == "applied"

        asyncio.run(_run())

    def test_approve_cross_tenant_returns_404(self, auth_a: AuthContext) -> None:
        """跨租户 approve 返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.memory_proposals import approve_proposal

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await approve_proposal(proposal_id=1, auth=auth_a, session=session)
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_approve_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """只有 memory:write scope 才能 approve。"""
        from src.api.router.memory_proposals import approve_proposal

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await approve_proposal(proposal_id=1, auth=auth_readonly, session=FakeDBSession())
            assert exc_info.value.status_code == 403

        asyncio.run(_run())

    def test_approve_already_approved_returns_409(self, auth_a: AuthContext) -> None:
        """已审批的提案不能再次审批。"""
        from src.api.router.memory_proposals import approve_proposal

        proposal = _make_proposal(id=1, status="applied")
        session = FakeDBSession(scalars_first_return=proposal)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await approve_proposal(proposal_id=1, auth=auth_a, session=session)
            assert exc_info.value.status_code == 409

        asyncio.run(_run())


# ============================================================================
# Reject Tests
# ============================================================================


class TestRejectProposal:
    """测试审批拒绝。"""

    def test_reject_requires_reason(self, auth_a: AuthContext) -> None:
        """拒绝必须填写理由。"""
        from src.api.router.memory_proposals import reject_proposal
        from src.api.schema.memory_proposals import RejectRequest

        proposal = _make_proposal(id=1, status="pending")
        session = FakeDBSession(scalars_first_return=proposal)

        async def _run() -> None:
            result = await reject_proposal(
                proposal_id=1,
                request=RejectRequest(reason="信息不准确，需要人工核实"),
                auth=auth_a,
                session=session,
            )
            assert result.code == 200
            assert proposal.status == "rejected"
            assert proposal.review_reason == "信息不准确，需要人工核实"
            assert proposal.reviewed_by == "user-a"

        asyncio.run(_run())

    def test_reject_cross_tenant_returns_404(self, auth_a: AuthContext) -> None:
        """跨租户 reject 返回 404（SQL 层过滤，DB 视角无行）。"""
        from src.api.router.memory_proposals import reject_proposal
        from src.api.schema.memory_proposals import RejectRequest

        session = FakeDBSession(scalars_first_return=None)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await reject_proposal(
                    proposal_id=1,
                    request=RejectRequest(reason="不通过"),
                    auth=auth_a,
                    session=session,
                )
            assert exc_info.value.status_code == 404

        asyncio.run(_run())

    def test_reject_already_rejected_returns_409(self, auth_a: AuthContext) -> None:
        """已拒绝的提案不能再次拒绝。"""
        from src.api.router.memory_proposals import reject_proposal
        from src.api.schema.memory_proposals import RejectRequest

        proposal = _make_proposal(id=1, status="rejected")
        session = FakeDBSession(scalars_first_return=proposal)

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await reject_proposal(
                    proposal_id=1,
                    request=RejectRequest(reason="再次拒绝"),
                    auth=auth_a,
                    session=session,
                )
            assert exc_info.value.status_code == 409

        asyncio.run(_run())

    def test_reject_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """只有 memory:write scope 才能 reject。"""
        from src.api.router.memory_proposals import reject_proposal
        from src.api.schema.memory_proposals import RejectRequest

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await reject_proposal(
                    proposal_id=1,
                    request=RejectRequest(reason="不通过"),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ============================================================================
# Distill Tests
# ============================================================================


class TestDistill:
    """测试手动提炼 API。"""

    def test_distill_task_completion(self, auth_a: AuthContext) -> None:
        """手动触发 task_completion 提炼。"""
        from src.api.router.memory_proposals import distill
        from src.api.schema.memory_proposals import DistillRequest

        session = FakeDBSession()

        async def _run() -> None:
            result = await distill(
                request=DistillRequest(
                    source_type="task_completion",
                    source_ref="task-001",
                    generation_result={
                        "selling_points": ["简洁构图"],
                        "quality_review": {"issues": ["过曝"]},
                        "category": "digital",
                    },
                    category="digital",
                ),
                auth=auth_a,
                session=session,
            )
            assert result.code == 200
            assert result.message == "提炼成功"
            assert result.data is not None

        asyncio.run(_run())

    def test_distill_no_content_returns_400(self, auth_a: AuthContext) -> None:
        """无可提炼内容时返回 400。"""
        from src.api.router.memory_proposals import distill
        from src.api.schema.memory_proposals import DistillRequest

        session = FakeDBSession()

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await distill(
                    request=DistillRequest(
                        source_type="task_completion",
                        source_ref="task-empty",
                        generation_result={},
                        category="digital",
                    ),
                    auth=auth_a,
                    session=session,
                )
            assert exc_info.value.status_code == 400

        asyncio.run(_run())

    def test_distill_requires_write_scope(self, auth_readonly: AuthContext) -> None:
        """只有 memory:write scope 才能 distill。"""
        from src.api.router.memory_proposals import distill
        from src.api.schema.memory_proposals import DistillRequest

        async def _run() -> None:
            with pytest.raises(HTTPException) as exc_info:
                await distill(
                    request=DistillRequest(
                        source_type="task_completion",
                        source_ref="task-001",
                        generation_result={"selling_points": ["测试"]},
                        category="digital",
                    ),
                    auth=auth_readonly,
                    session=FakeDBSession(),
                )
            assert exc_info.value.status_code == 403

        asyncio.run(_run())
