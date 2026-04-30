"""工作流真实接线测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        workflow = ListingWorkflow()

        result = await workflow.run(
            product=product,
            target_platforms=[Platform.AMAZON],
            thread_id="wf-test-001",
        )

        assert result is not None
        assert result.get("current_step") == "compliance_checked"
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

            result = await workflow.run(
                product=product,
                target_platforms=[Platform.AMAZON],
                thread_id="wf-test-002",
            )

            mock_agent.execute_sync.assert_called_once()
