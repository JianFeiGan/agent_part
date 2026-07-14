"""
刊登工作流构建器。

Description:
    基于 LangGraph StateGraph 构建刊登工作流，
    真实调用各 Agent：素材优化、文案生成（LLM）、合规检查、平台推送。
    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → PlatformPush → END
@author ganjianfei
@version 2.0.0
2026-07-14
"""

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_compliance_checker import ComplianceCheckerAgent
from src.agents.listing_copywriter import AICopywritingAgent
from src.agents.listing_push_service import ListingPushService
from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, ListingTask, Platform, TaskStatus

logger = logging.getLogger(__name__)


class ListingWorkflow:
    """刊登工作流封装。

    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → PlatformPush → END
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化工作流。"""
        self._settings = settings
        self._builder = StateGraph(ListingState)
        self._build_graph()
        self._checkpointer = MemorySaver()
        self.app = self._builder.compile(checkpointer=self._checkpointer)

    def _build_graph(self) -> None:
        """构建状态图。"""
        self._builder.add_node("import_product", self._import_node)
        self._builder.add_node("optimize_assets", self._asset_optimize_node)
        self._builder.add_node("generate_copy", self._copy_node)
        self._builder.add_node("compliance_check", self._compliance_node)
        self._builder.add_node("platform_push", self._push_node)

        self._builder.set_entry_point("import_product")
        self._builder.add_edge("import_product", "optimize_assets")
        self._builder.add_edge("import_product", "generate_copy")
        self._builder.add_edge("optimize_assets", "compliance_check")
        self._builder.add_edge("generate_copy", "compliance_check")
        self._builder.add_edge("compliance_check", "platform_push")
        self._builder.add_edge("platform_push", END)

    async def _import_node(self, state: ListingState) -> dict:
        """商品导入节点。"""
        if state.product:
            return {"product": state.product}
        return {"error": "No product provided"}

    async def _asset_optimize_node(self, state: ListingState) -> dict:
        """素材优化节点：调用 AssetOptimizerAgent。"""
        if not state.product:
            return {"error": "No product available for asset optimization"}

        try:
            agent = AssetOptimizerAgent(settings=self._settings)
            result = agent.execute_sync(state)
            return {"asset_packages": result.get("asset_packages", state.asset_packages)}
        except Exception as e:
            logger.error(f"Asset optimization failed: {e}")
            return {"asset_packages": state.asset_packages}

    async def _copy_node(self, state: ListingState) -> dict:
        """文案生成节点：调用 AICopywritingAgent（含 LLM）。"""
        if not state.product:
            return {"error": "No product available for copywriting"}

        try:
            agent = AICopywritingAgent(settings=self._settings)
            result = await agent.execute(state)
            return {"copywriting_packages": result.get("copywriting_packages", {})}
        except Exception as e:
            logger.error(f"Copywriting generation failed: {e}")
            return {"copywriting_packages": {}}

    async def _compliance_node(self, state: ListingState) -> dict:
        """合规检查节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "compliance_failed"}
        agent = ComplianceCheckerAgent(settings=self._settings)
        result = agent.execute_sync(state)
        return {
            "compliance_reports": result.get("compliance_reports", {}),
            "current_step": "compliance_checked",
        }

    async def _push_node(self, state: ListingState) -> dict:
        """平台推送节点：调用 ListingPushService 并行推送到各平台。"""
        if not state.product:
            return {"error": "No product available", "current_step": "push_failed"}

        try:
            push_service = ListingPushService()
            task = ListingTask(
                product_id=state.product.id or 0,
                target_platforms=state.target_platforms,
                status=TaskStatus.PUSHING,
            )

            push_results = await push_service.push_to_platforms(
                product=state.product,
                asset_packages=state.asset_packages,
                copywriting_packages=state.copywriting_packages,
                task=task,
            )

            # 检查是否全部成功
            all_success = all(r.success for r in push_results.values())
            current_step = "push_completed" if all_success else "push_partial"

            return {
                "push_results": push_results,
                "current_step": current_step,
            }

        except Exception as e:
            logger.error(f"Platform push failed: {e}")
            return {
                "error": str(e),
                "current_step": "push_failed",
            }

    async def run(
        self,
        product: ListingProduct,
        target_platforms: list[Platform],
        thread_id: str = "default",
    ) -> dict:
        """执行刊登工作流。"""
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = ListingState(
            product=product,
            target_platforms=target_platforms,
        )
        return await self.app.ainvoke(initial_state, config=config)
