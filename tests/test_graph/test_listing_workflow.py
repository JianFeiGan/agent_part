"""工作流真实接线测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.listing_platform_adapter import PushResult
from src.graph.listing_workflow import ListingWorkflow
from src.models.listing import AssetPackage, ListingProduct, Platform


@pytest.fixture
def product() -> ListingProduct:
    return ListingProduct(
        sku="WF-TEST-001",
        title="Test Product",
        description="A test product for workflow",
        category="Test",
        brand="TestBrand",
    )


class TestListingWorkflow:
    """测试工作流真实执行。"""

    @pytest.mark.asyncio
    async def test_full_workflow(self, product: ListingProduct) -> None:
        """测试完整工作流。"""
        # Mock ListingPushService 以避免需要注册适配器
        with patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls:
            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True,
                        platform=Platform.AMAZON,
                        listing_id="test-listing",
                    ),
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()

            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-test-001",
            )

            assert result is not None
            # finalize 节点统一收口，终态写入 step_results
            assert result.get("current_step") == "finalized"
            assert result.get("step_results", {}).get("final_status") == "published"
            assert result.get("copywriting_packages")
            assert Platform.AMAZON in result.get("copywriting_packages", {})

    @pytest.mark.asyncio
    async def test_asset_optimize_calls_real_agent(self, product: ListingProduct) -> None:
        """测试素材优化节点调用真实 Agent。"""
        with patch("src.graph.listing_workflow.AssetOptimizerAgent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.execute_sync = MagicMock(
                return_value={
                    "asset_packages": {
                        Platform.AMAZON: AssetPackage(
                            listing_task_id=1,
                            platform=Platform.AMAZON,
                            main_image="https://example.com/test.jpg",
                        )
                    },
                }
            )
            mock_agent_cls.return_value = mock_agent

            workflow = ListingWorkflow()

            await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-test-002",
            )

            mock_agent.execute_sync.assert_called_once()

    @pytest.mark.asyncio
    async def test_import_failure_routes_to_finalize(self) -> None:
        """无商品时快速终止：不生成文案、不推送，终态 failed。"""
        with patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls:
            workflow = ListingWorkflow()

            result = await workflow.run(
                product=None,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-fail-001",
            )

            assert result.get("current_step") == "finalized"
            assert result.get("step_results", {}).get("final_status") == "failed"
            assert result.get("error") == "No product provided"
            assert not result.get("copywriting_packages")
            mock_push_cls.return_value.push_to_platforms.assert_not_called()

    @pytest.mark.asyncio
    async def test_asset_optimize_error_is_recorded(
        self, product: ListingProduct
    ) -> None:
        """素材优化异常记入 state.errors，流程继续（文案仍生成）。"""
        with (
            patch("src.graph.listing_workflow.AssetOptimizerAgent") as mock_agent_cls,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            mock_agent = MagicMock()
            mock_agent.execute_sync = MagicMock(side_effect=RuntimeError("optimizer boom"))
            mock_agent_cls.return_value = mock_agent

            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True, platform=Platform.AMAZON, listing_id="L-1"
                    )
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-err-001",
            )

            errors = result.get("errors", [])
            assert any(e["node"] == "optimize_assets" for e in errors)
            # 文案节点不受影响，正常产出
            assert result.get("copywriting_packages")

    @pytest.mark.asyncio
    async def test_compliance_fail_parks_reviewing(
        self, product: ListingProduct
    ) -> None:
        """合规 FAIL → 不推送，任务挂起 reviewing。"""
        from src.models.listing import ComplianceReport, ComplianceStatus

        fail_report = ComplianceReport(
            listing_task_id=0,
            platform=Platform.AMAZON,
            overall=ComplianceStatus.FAIL,
        )

        with (
            patch("src.graph.listing_workflow.ComplianceCheckerAgent") as mock_checker_cls,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            mock_checker = MagicMock()
            mock_checker.execute_sync = MagicMock(
                return_value={"compliance_reports": {Platform.AMAZON: fail_report}}
            )
            mock_checker_cls.return_value = mock_checker

            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-review-001",
            )

            assert result.get("blocked_platforms") == [Platform.AMAZON]
            assert result.get("step_results", {}).get("final_status") == "reviewing"
            mock_push_cls.return_value.push_to_platforms.assert_not_called()

    @pytest.mark.asyncio
    async def test_compliance_pass_proceeds_to_push(
        self, product: ListingProduct
    ) -> None:
        """合规全部通过 → 正常推送，终态 published。"""
        with patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls:
            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True, platform=Platform.AMAZON, listing_id="L-2"
                    )
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-pass-001",
            )

            assert result.get("blocked_platforms") == []
            assert result.get("step_results", {}).get("final_status") == "published"
            mock_push.push_to_platforms.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_auto_retries_transient_failure(
        self, product: ListingProduct
    ) -> None:
        """推送遇非永久错误自动重试一次，重试成功则终态 published。"""
        transient = PushResult(
            success=False, platform=Platform.AMAZON, error="timeout", error_code="HTTP_503"
        )
        retried = PushResult(success=True, platform=Platform.AMAZON, listing_id="L-3")

        mock_push = MagicMock()
        mock_push.push_to_platforms = AsyncMock(return_value={"amazon": transient})
        mock_push.retry_failed = AsyncMock(return_value={"amazon": retried})

        with patch("src.graph.listing_workflow.ListingPushService", return_value=mock_push):
            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-retry-001",
            )

        mock_push.retry_failed.assert_called_once()
        assert result["push_results"]["amazon"].success is True
        assert result["step_results"]["final_status"] == "published"

    @pytest.mark.asyncio
    async def test_push_no_retry_when_all_success(
        self, product: ListingProduct
    ) -> None:
        """全部成功时不触发重试。"""
        mock_push = MagicMock()
        mock_push.push_to_platforms = AsyncMock(
            return_value={
                "amazon": PushResult(success=True, platform=Platform.AMAZON, listing_id="L-4")
            }
        )
        mock_push.retry_failed = AsyncMock()

        with patch("src.graph.listing_workflow.ListingPushService", return_value=mock_push):
            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-noretry-001",
            )

        mock_push.retry_failed.assert_not_called()
        assert result["step_results"]["final_status"] == "published"

    @pytest.mark.asyncio
    async def test_push_all_failed_gives_failed_status(
        self, product: ListingProduct
    ) -> None:
        """重试后仍全部失败 → 终态 failed。"""
        failure = PushResult(
            success=False, platform=Platform.AMAZON, error="boom", error_code="HTTP_500"
        )
        mock_push = MagicMock()
        mock_push.push_to_platforms = AsyncMock(return_value={"amazon": failure})
        mock_push.retry_failed = AsyncMock(return_value={"amazon": failure})

        with patch("src.graph.listing_workflow.ListingPushService", return_value=mock_push):
            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-allfail-001",
            )

        mock_push.retry_failed.assert_called_once()
        assert result["step_results"]["final_status"] == "failed"
