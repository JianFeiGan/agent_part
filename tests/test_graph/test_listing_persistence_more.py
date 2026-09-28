"""刊登持久化补充行为测试。

覆盖素材/文案/合规/推送的 upsert 与 load 路径、best-effort 异常吞掉、
租户过滤不匹配的跳过分支。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.listing_platform_adapter import PushResult
from src.graph import listing_persistence
from src.models.listing import (
    AssetPackage,
    ComplianceReport,
    ComplianceStatus,
    CopywritingPackage,
    Platform,
)

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _session_cm(session: AsyncMock) -> AsyncMock:
    """构造 async with 会话上下文。"""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _session_with(one_or_none: Any = None, all_items: list[Any] | None = None) -> AsyncMock:
    """构造返回固定结果的会话。"""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=one_or_none)
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=all_items or [])
    result.scalars = MagicMock(return_value=scalars)
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    return session


@pytest.fixture
def patched_session(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """注入会话：execute 默认返回空结果（走插入分支）。"""
    session = _session_with(one_or_none=None)
    monkeypatch.setattr(listing_persistence, "get_db_session", lambda: _session_cm(session))
    return session


class TestUpdateTaskStatus:
    """update_task_status。"""

    async def test_missing_task_skipped(self, patched_session: AsyncMock) -> None:
        """任务不存在时跳过更新。"""
        patched_session.get = AsyncMock(return_value=None)

        await listing_persistence.update_task_status(9, "t1", "published")

        patched_session.get.assert_awaited_once()

    async def test_exception_is_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """数据库异常不阻断工作流。"""

        class _Broken:
            async def __aenter__(self) -> Any:
                raise RuntimeError("db down")

            async def __aexit__(self, *exc: Any) -> None:
                return None

        monkeypatch.setattr(listing_persistence, "get_db_session", _Broken)

        await listing_persistence.update_task_status(1, "t1", "failed")


class TestSavePackages:
    """素材 / 文案 / 合规 / 推送 落库。"""

    async def test_save_asset_packages_upserts_existing(self, patched_session: AsyncMock) -> None:
        """已存在素材包时覆盖字段而非新建。"""
        po = MagicMock()
        patched_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=po))
        )

        await listing_persistence.save_asset_packages(
            1,
            "t1",
            {
                Platform.AMAZON: AssetPackage(
                    listing_task_id=1, platform=Platform.AMAZON, main_image="m.png"
                )
            },
        )

        assert po.main_image == "m.png"
        patched_session.add.assert_not_called()

    async def test_save_copywriting_packages(self, patched_session: AsyncMock) -> None:
        """文案包 upsert 写入标题/要点/描述/搜索词。"""
        pkg = CopywritingPackage(
            listing_task_id=1,
            platform=Platform.AMAZON,
            language="en-US",
            title="Title",
            bullet_points=["b1", "b2"],
            description="desc",
            search_terms=["kw"],
        )

        await listing_persistence.save_copywriting_packages(1, "t1", {Platform.AMAZON: pkg})

        added = patched_session.add.call_args.args[0]
        assert added.title == "Title"
        assert added.bullet_points == ["b1", "b2"]
        assert added.search_terms == ["kw"]

    async def test_save_compliance_reports(self, patched_session: AsyncMock) -> None:
        """合规报告整体判定与问题清单一并落库。"""
        report = ComplianceReport(
            listing_task_id=1,
            platform=Platform.EBAY,
            overall=ComplianceStatus.FAIL,
            forbidden_words=["best"],
        )

        await listing_persistence.save_compliance_reports(1, "t1", {Platform.EBAY: report})

        added = patched_session.add.call_args.args[0]
        assert added.report_data["overall"] == "fail"
        assert added.report_data["forbidden_words"] == ["best"]

    async def test_save_push_results_records_error_detail(self, patched_session: AsyncMock) -> None:
        """推送失败时错误码与重试次数写入 result_data。"""
        result = PushResult(
            platform=Platform.SHOPIFY,
            success=False,
            error="timeout",
            error_code="E504",
            retry_count=2,
            latency_ms=120,
        )

        await listing_persistence.save_push_results(1, "t1", {"shopify": result})

        added = patched_session.add.call_args.args[0]
        assert added.success is False
        assert added.result_data["error_code"] == "E504"
        assert added.result_data["retry_count"] == 2

    @pytest.mark.parametrize(
        "fn,args",
        [
            ("save_asset_packages", (1, "t1", {})),
            ("save_copywriting_packages", (1, "t1", {})),
            ("save_compliance_reports", (1, "t1", {})),
            ("save_push_results", (1, "t1", {})),
        ],
    )
    async def test_empty_input_is_noop(
        self, monkeypatch: pytest.MonkeyPatch, fn: str, args: tuple[Any, ...]
    ) -> None:
        """空集合直接返回，不触碰数据库。"""

        class _NoSession:
            async def __aenter__(self) -> Any:
                raise AssertionError("不应访问数据库")

            async def __aexit__(self, *exc: Any) -> None:
                return None

        monkeypatch.setattr(listing_persistence, "get_db_session", _NoSession)
        await getattr(listing_persistence, fn)(*args)

    async def test_save_failure_is_swallowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """文案落库失败仅记日志。"""

        class _Broken:
            async def __aenter__(self) -> Any:
                raise RuntimeError("db down")

            async def __aexit__(self, *exc: Any) -> None:
                return None

        monkeypatch.setattr(listing_persistence, "get_db_session", _Broken)

        await listing_persistence.save_copywriting_packages(
            1,
            "t1",
            {Platform.AMAZON: CopywritingPackage(listing_task_id=1, platform=Platform.AMAZON)},
        )


class TestLoaders:
    """load_* 查询。"""

    async def test_load_asset_packages(self, patched_session: AsyncMock) -> None:
        """素材包按平台还原为领域对象。"""
        po = MagicMock()
        po.id = 7
        po.task_id = 1
        po.platform = "amazon"
        po.main_image = "m.png"
        po.variant_images = ["v1.png"]
        po.video_url = None
        po.a_plus_images = []
        patched_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[po])))
            )
        )

        packages = await listing_persistence.load_asset_packages(1, "t1")

        assert set(packages) == {Platform.AMAZON}
        assert packages[Platform.AMAZON].main_image == "m.png"
        assert packages[Platform.AMAZON].variant_images == ["v1.png"]

    async def test_load_copywriting_packages_defaults(self, patched_session: AsyncMock) -> None:
        """文案包缺省字段回落为空列表。"""
        po = MagicMock()
        po.id = 3
        po.task_id = 1
        po.platform = "ebay"
        po.language = "en-US"
        po.title = "T"
        po.bullet_points = None
        po.description = "D"
        po.search_terms = None
        patched_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[po])))
            )
        )

        packages = await listing_persistence.load_copywriting_packages(1, "t1")

        assert packages[Platform.EBAY].bullet_points == []
        assert packages[Platform.EBAY].search_terms == []

    async def test_load_blocked_platforms_only_fail(self, patched_session: AsyncMock) -> None:
        """仅 overall=fail 的平台被列为阻断。"""
        pass_po = MagicMock()
        pass_po.platform = "amazon"
        pass_po.report_data = {"overall": "pass"}
        fail_po = MagicMock()
        fail_po.platform = "ebay"
        fail_po.report_data = {"overall": "fail"}
        patched_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[pass_po, fail_po]))
                )
            )
        )

        blocked = await listing_persistence.load_blocked_platforms(1, "t1")

        assert blocked == {Platform.EBAY}

    async def test_load_push_result_statuses(self, patched_session: AsyncMock) -> None:
        """推送结果映射为 {platform: success}。"""
        ok = MagicMock()
        ok.platform = "amazon"
        ok.success = True
        bad = MagicMock()
        bad.platform = "shopify"
        bad.success = False
        patched_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[ok, bad])))
            )
        )

        statuses = await listing_persistence.load_push_result_statuses(1, "t1")

        assert statuses == {"amazon": True, "shopify": False}

    async def test_load_asset_packages_empty(self, patched_session: AsyncMock) -> None:
        """无记录返回空 dict。"""
        patched_session.execute = AsyncMock(
            return_value=MagicMock(
                scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
            )
        )

        assert await listing_persistence.load_asset_packages(1, "t1") == {}
