"""
MemoryDistiller 测试。

Description:
    测试 MemoryDistiller 的三种提炼方法：
    - distill_from_task
    - distill_from_compliance
    - distill_from_push_result
    验证提炼规则、confidence 计算、不直接写 CategoryMemory。
@author ganjianfei
@version 1.0.0
2026-06-19
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import pytest

from src.db.models import CategoryMemoryProposalPO
from src.rag.memory_distiller import MemoryDistiller


class FakeAsyncSession:
    """模拟 AsyncSession，仅记录 add 调用和 flush。"""

    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


@pytest.fixture
def distiller() -> MemoryDistiller:
    """创建 MemoryDistiller 实例。"""
    return MemoryDistiller()


@pytest.fixture
def session() -> FakeAsyncSession:
    """创建模拟 session。"""
    return FakeAsyncSession()


class TestDistillFromTask:
    """测试 distill_from_task 方法。"""

    @pytest.mark.asyncio
    async def test_creates_proposal_when_selling_points(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """有 selling_points 时应创建 proposal。"""
        gen_result = {
            "selling_points": ["白色背景", "细节清晰"],
            "category": "digital",
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-001", gen_result, "digital",
        )

        assert proposal is not None
        assert isinstance(proposal, CategoryMemoryProposalPO)
        assert proposal.tenant_id == "tenant-a"
        assert proposal.category == "digital"
        assert len(proposal.best_practices) == 2
        assert "白色背景" in proposal.best_practices
        assert "细节清晰" in proposal.best_practices
        assert proposal.source_type == "task_completion"
        assert proposal.source_ref == "task-001"
        assert proposal.status == "pending"
        assert proposal.confidence == 0.5  # only selling_points, no quality_review

        assert len(session.added) == 1
        assert session.flushed is True

    @pytest.mark.asyncio
    async def test_creates_proposal_with_negative_patterns(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """有 quality_review issues 时应提炼到 negative_patterns。"""
        gen_result = {
            "quality_review": {
                "issues": ["过曝问题", "色彩失真"],
            },
            "category": "digital",
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-002", gen_result, "digital",
        )

        assert proposal is not None
        assert len(proposal.negative_patterns) == 2
        assert "过曝问题" in proposal.negative_patterns
        assert "色彩失真" in proposal.negative_patterns
        assert proposal.confidence == 0.5  # only quality_review, no selling_points

    @pytest.mark.asyncio
    async def test_full_completion_gives_confidence_1(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """同时有 selling_points 和 quality_review 时 confidence=1.0。"""
        gen_result = {
            "selling_points": ["突出细节"],
            "quality_review": {"issues": ["暗角问题"]},
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-003", gen_result, "digital",
        )

        assert proposal is not None
        assert proposal.confidence == 1.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_actionable_content(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """无可提炼内容时返回 None。"""
        gen_result: dict[str, Any] = {}

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-004", gen_result, "digital",
        )

        assert proposal is None
        assert len(session.added) == 0

    @pytest.mark.asyncio
    async def test_handles_dict_selling_points(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """selling_points 中的 dict 项应提取 text/content/description 字段。"""
        gen_result = {
            "selling_points": [
                {"text": "突出产品质感"},
                {"content": "简洁构图"},
            ],
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-005", gen_result, "digital",
        )

        assert proposal is not None
        assert "突出产品质感" in proposal.best_practices
        assert "简洁构图" in proposal.best_practices

    @pytest.mark.asyncio
    async def test_handles_dict_issues(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """quality_review issues 中的 dict 项应提取 description。"""
        gen_result = {
            "quality_review": {
                "issues": [
                    {"description": "图片模糊"},
                    {"issue": "色彩偏差"},
                ],
            },
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-006", gen_result, "digital",
        )

        assert proposal is not None
        assert "图片模糊" in proposal.negative_patterns
        assert "色彩偏差" in proposal.negative_patterns

    @pytest.mark.asyncio
    async def test_does_not_write_category_memory_directly(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """验证 distiller 不直接写 CategoryMemoryPO。"""
        gen_result = {
            "selling_points": ["测试"],
        }

        proposal = await distiller.distill_from_task(
            session, "tenant-a", "task-007", gen_result, "digital",
        )

        assert proposal is not None
        assert isinstance(proposal, CategoryMemoryProposalPO)
        # 确认 session 中只有 CategoryMemoryProposalPO 被 add
        for obj in session.added:
            assert isinstance(obj, CategoryMemoryProposalPO)


class TestDistillFromCompliance:
    """测试 distill_from_compliance 方法。"""

    @pytest.mark.asyncio
    async def test_creates_proposal_with_negative_patterns(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """合规报告应提炼违规和禁词到 negative_patterns。"""
        compliance_report = {
            "report_id": "cr-001",
            "category": "digital",
            "violations": [
                "使用夸大宣传用语",
                {"rule": "图片包含未授权商标"},
            ],
            "banned_words": ["最好", "第一"],
        }

        proposal = await distiller.distill_from_compliance(
            session, "tenant-a", compliance_report,
        )

        assert proposal is not None
        assert isinstance(proposal, CategoryMemoryProposalPO)
        assert proposal.source_type == "compliance_failure"
        assert proposal.source_ref == "cr-001"
        assert proposal.confidence == 0.8
        assert len(proposal.negative_patterns) >= 2
        assert "使用夸大宣传用语" in proposal.negative_patterns
        assert "图片包含未授权商标" in proposal.negative_patterns
        assert "禁用词: 最好" in proposal.negative_patterns
        assert "禁用词: 第一" in proposal.negative_patterns

    @pytest.mark.asyncio
    async def test_returns_none_when_no_violations(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """无违规内容时返回 None。"""
        compliance_report = {
            "report_id": "cr-002",
            "category": "digital",
            "violations": [],
            "banned_words": [],
        }

        proposal = await distiller.distill_from_compliance(
            session, "tenant-a", compliance_report,
        )

        assert proposal is None


class TestDistillFromPushResult:
    """测试 distill_from_push_result 方法。"""

    @pytest.mark.asyncio
    async def test_creates_proposal_with_best_practices(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """推送结果中的高表现指标应提炼到 best_practices。"""
        push_result = {
            "listing_id": "lst-001",
            "category": "digital",
            "high_performance": {
                "ctr": "高点击率: 5.2%",
                "conversion": "高转化: 3.1%",
            },
        }

        proposal = await distiller.distill_from_push_result(
            session, "tenant-a", push_result,
        )

        assert proposal is not None
        assert isinstance(proposal, CategoryMemoryProposalPO)
        assert proposal.source_type == "platform_push"
        assert proposal.source_ref == "lst-001"
        assert proposal.confidence == 0.6
        assert len(proposal.best_practices) == 2

    @pytest.mark.asyncio
    async def test_creates_proposal_with_performance_hints(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """推送结果中的 metrics 应提炼到 performance_hints。"""
        push_result = {
            "id": "lst-002",
            "category": "digital",
            "metrics": {
                "impressions": 15000,
                "clicks": 450,
                "ctr": 3.0,
            },
        }

        proposal = await distiller.distill_from_push_result(
            session, "tenant-a", push_result,
        )

        assert proposal is not None
        assert proposal.performance_hints["impressions"] == 15000
        assert proposal.performance_hints["ctr"] == 3.0

    @pytest.mark.asyncio
    async def test_returns_none_when_no_usable_data(
        self, distiller: MemoryDistiller, session: FakeAsyncSession
    ) -> None:
        """无可用数据时返回 None。"""
        push_result = {
            "listing_id": "lst-003",
            "category": "digital",
        }

        proposal = await distiller.distill_from_push_result(
            session, "tenant-a", push_result,
        )

        assert proposal is None
