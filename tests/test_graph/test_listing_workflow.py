"""工作流真实接线测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.listing_platform_adapter import PushResult
from src.graph.listing_workflow import ListingWorkflow
from src.models.listing import (
    AssetPackage,
    CopywritingPackage,
    ListingProduct,
    Platform,
)


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

    @pytest.mark.asyncio
    async def test_workflow_persists_each_stage(
        self, product: ListingProduct
    ) -> None:
        """task_id 非空时：状态流转与各阶段产物均持久化。"""
        with (
            patch("src.graph.listing_workflow.listing_persistence") as mock_persist,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            for name in (
                "update_task_status",
                "save_asset_packages",
                "save_copywriting_packages",
                "save_compliance_reports",
                "save_push_results",
            ):
                setattr(mock_persist, name, AsyncMock())

            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True, platform=Platform.AMAZON, listing_id="L-5"
                    )
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-persist-001",
                task_id=99,
                tenant_id="tenant-x",
            )

            # 状态流转：generating → pushing → published
            statuses = [
                c.args[2] for c in mock_persist.update_task_status.call_args_list
            ]
            assert statuses == ["generating", "pushing", "published"]

            mock_persist.save_asset_packages.assert_called_once()
            mock_persist.save_copywriting_packages.assert_called_once()
            mock_persist.save_compliance_reports.assert_called_once()
            mock_persist.save_push_results.assert_called_once()
            # 租户 ID 贯穿
            assert mock_persist.save_push_results.call_args.args[1] == "tenant-x"
            assert result["step_results"]["final_status"] == "published"

    @pytest.mark.asyncio
    async def test_workflow_without_task_id_skips_persistence(
        self, product: ListingProduct
    ) -> None:
        """task_id 为 None（纯内存运行）时不触碰持久化。"""
        with (
            patch("src.graph.listing_workflow.listing_persistence") as mock_persist,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            for name in (
                "update_task_status",
                "save_asset_packages",
                "save_copywriting_packages",
                "save_compliance_reports",
                "save_push_results",
            ):
                setattr(mock_persist, name, AsyncMock())

            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True, platform=Platform.AMAZON, listing_id="L-6"
                    )
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-nopersist-001",
            )

            mock_persist.update_task_status.assert_not_called()
            mock_persist.save_asset_packages.assert_not_called()
            mock_persist.save_push_results.assert_not_called()


class TestResumePush:
    """人工审核后恢复推送。"""

    @pytest.mark.asyncio
    async def test_resume_push_success(self) -> None:
        """恢复推送：推送指定平台并按累计结果计算终态。"""
        task_po = MagicMock()
        task_po.tenant_id = "t1"
        task_po.product_sku = "SKU-1"
        task_po.target_platforms = ["amazon", "ebay"]

        product_po = MagicMock()
        product_po.id = 7
        product_po.sku = "SKU-1"
        product_po.title = "Resume Product"
        product_po.description = "desc"
        product_po.category = "Cat"
        product_po.brand = "Brand"
        product_po.source_images = []
        product_po.attributes = {}

        session = AsyncMock()
        session.get = AsyncMock(return_value=task_po)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = product_po
        session.execute = AsyncMock(return_value=exec_result)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        asset_pkg = AssetPackage(
            listing_task_id=1, platform=Platform.AMAZON, main_image="https://x/m.jpg"
        )
        copy_pkg = CopywritingPackage(
            listing_task_id=1, platform=Platform.AMAZON, title="Resume Product"
        )

        with (
            patch("src.graph.listing_workflow.get_db_session", return_value=cm),
            patch("src.graph.listing_workflow.listing_persistence") as mock_persist,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            mock_persist.load_asset_packages = AsyncMock(
                return_value={Platform.AMAZON: asset_pkg}
            )
            mock_persist.load_copywriting_packages = AsyncMock(
                return_value={Platform.AMAZON: copy_pkg}
            )
            mock_persist.update_task_status = AsyncMock()
            mock_persist.save_push_results = AsyncMock()
            mock_persist.load_push_result_statuses = AsyncMock(
                return_value={"amazon": True, "ebay": True}
            )

            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(
                return_value={
                    "amazon": PushResult(
                        success=True, platform=Platform.AMAZON, listing_id="L-7"
                    ),
                    "ebay": PushResult(
                        success=True, platform=Platform.EBAY, listing_id="E-7"
                    ),
                }
            )
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            outcome = await workflow.resume_push(
                task_id=1,
                tenant_id="t1",
                platforms=[Platform.AMAZON, Platform.EBAY],
            )

            assert outcome["final_status"] == "published"
            assert outcome["push_results"]["amazon"].success is True
            # 末次状态更新为终态
            last_status_call = mock_persist.update_task_status.call_args_list[-1]
            assert last_status_call.args[2] == "published"

    @pytest.mark.asyncio
    async def test_resume_push_all_failed_back_to_reviewing(self) -> None:
        """恢复推送全部失败 → 回到 reviewing 保持挂起。"""
        task_po = MagicMock()
        task_po.tenant_id = "t1"
        task_po.product_sku = "SKU-1"
        task_po.target_platforms = ["amazon"]

        product_po = MagicMock()
        product_po.id = 7
        product_po.sku = "SKU-1"
        product_po.title = "P"
        product_po.description = None
        product_po.category = None
        product_po.brand = None
        product_po.source_images = []
        product_po.attributes = {}

        session = AsyncMock()
        session.get = AsyncMock(return_value=task_po)
        exec_result = MagicMock()
        exec_result.scalar_one_or_none.return_value = product_po
        session.execute = AsyncMock(return_value=exec_result)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        failure = PushResult(
            success=False, platform=Platform.AMAZON, error="boom", error_code="HTTP_500"
        )

        with (
            patch("src.graph.listing_workflow.get_db_session", return_value=cm),
            patch("src.graph.listing_workflow.listing_persistence") as mock_persist,
            patch("src.graph.listing_workflow.ListingPushService") as mock_push_cls,
        ):
            mock_persist.load_asset_packages = AsyncMock(return_value={})
            mock_persist.load_copywriting_packages = AsyncMock(return_value={})
            mock_persist.update_task_status = AsyncMock()
            mock_persist.save_push_results = AsyncMock()
            mock_persist.load_push_result_statuses = AsyncMock(
                return_value={"amazon": False}
            )

            mock_push = MagicMock()
            mock_push.push_to_platforms = AsyncMock(return_value={"amazon": failure})
            mock_push.retry_failed = AsyncMock(return_value={"amazon": failure})
            mock_push_cls.return_value = mock_push

            workflow = ListingWorkflow()
            outcome = await workflow.resume_push(
                task_id=1, tenant_id="t1", platforms=[Platform.AMAZON]
            )

            assert outcome["final_status"] == "reviewing"

    @pytest.mark.asyncio
    async def test_resume_push_task_not_found(self) -> None:
        """任务不存在或租户不匹配 → ValueError。"""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=session)
        cm.__aexit__ = AsyncMock(return_value=None)

        with patch("src.graph.listing_workflow.get_db_session", return_value=cm):
            workflow = ListingWorkflow()
            with pytest.raises(ValueError, match="不存在"):
                await workflow.resume_push(
                    task_id=999, tenant_id="t1", platforms=[Platform.AMAZON]
                )
