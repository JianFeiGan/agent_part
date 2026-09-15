"""刊登工作流持久化模块测试（mock DB 会话层）。"""

from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_session_cm(mock_session: AsyncMock) -> AsyncMock:
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_update_task_status() -> None:
    """更新任务状态并做租户校验。"""
    task = MagicMock()
    task.tenant_id = "t1"
    task.status = "reviewing"
    task.workflow_state = None
    session = AsyncMock()
    session.get = AsyncMock(return_value=task)

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        await listing_persistence.update_task_status(
            1, "t1", "published", workflow_state="finalized"
        )

    assert task.status == "published"
    assert task.workflow_state == "finalized"


@pytest.mark.asyncio
async def test_update_task_status_tenant_mismatch_skipped() -> None:
    """租户不匹配时不更新。"""
    task = MagicMock()
    task.tenant_id = "other"
    task.status = "reviewing"
    session = AsyncMock()
    session.get = AsyncMock(return_value=task)

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        await listing_persistence.update_task_status(1, "t1", "published")

    assert task.status == "reviewing"


@pytest.mark.asyncio
async def test_save_asset_packages_insert() -> None:
    """素材包不存在时插入新行。"""
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=exec_result)

    pkg = AssetPackage(
        listing_task_id=1,
        platform=Platform.AMAZON,
        main_image="https://example.com/m.jpg",
        variant_images=["https://example.com/v.jpg"],
    )

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        await listing_persistence.save_asset_packages(
            1, "t1", {Platform.AMAZON: pkg}
        )

    session.add.assert_called_once()
    po = session.add.call_args[0][0]
    assert po.task_id == 1
    assert po.tenant_id == "t1"
    assert po.platform == "amazon"
    assert po.main_image == "https://example.com/m.jpg"


@pytest.mark.asyncio
async def test_save_push_results_upsert_existing() -> None:
    """已有推送结果时更新而非重复插入。"""
    existing = MagicMock()
    existing.success = False
    existing.result_data = {}
    session = AsyncMock()
    exec_result = MagicMock()
    exec_result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=exec_result)

    result = PushResult(
        success=True,
        platform=Platform.AMAZON,
        listing_id="L-1",
        url="https://amazon.com/dp/L1",
        retry_count=1,
    )

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        await listing_persistence.save_push_results(1, "t1", {"amazon": result})

    session.add.assert_not_called()
    assert existing.success is True
    assert existing.result_data["listing_id"] == "L-1"
    assert existing.result_data["retry_count"] == 1


@pytest.mark.asyncio
async def test_load_blocked_platforms() -> None:
    """从合规报告 JSONB 中提取 overall=fail 的平台。"""
    fail_po = MagicMock()
    fail_po.platform = "ebay"
    fail_po.report_data = {"overall": "fail"}
    pass_po = MagicMock()
    pass_po.platform = "amazon"
    pass_po.report_data = {"overall": "pass"}

    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [fail_po, pass_po]
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=exec_result)

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        blocked = await listing_persistence.load_blocked_platforms(1, "t1")

    assert blocked == {Platform.EBAY}


@pytest.mark.asyncio
async def test_load_copywriting_packages() -> None:
    """加载文案包并还原为领域模型。"""
    po = MagicMock()
    po.id = 5
    po.task_id = 1
    po.platform = "amazon"
    po.language = "en"
    po.title = "Title"
    po.bullet_points = ["b1"]
    po.description = "desc"
    po.search_terms = ["kw"]

    session = AsyncMock()
    scalars = MagicMock()
    scalars.all.return_value = [po]
    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=exec_result)

    with patch.object(
        listing_persistence, "get_db_session", return_value=_make_session_cm(session)
    ):
        packages = await listing_persistence.load_copywriting_packages(1, "t1")

    assert packages[Platform.AMAZON].title == "Title"
    assert packages[Platform.AMAZON].listing_task_id == 1


@pytest.mark.asyncio
async def test_save_failure_is_best_effort() -> None:
    """DB 异常只记日志不抛出（best-effort）。"""
    with patch.object(
        listing_persistence, "get_db_session", side_effect=RuntimeError("db down")
    ):
        # 不应抛出
        await listing_persistence.save_asset_packages(1, "t1", {})
