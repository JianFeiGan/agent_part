"""
刊登工作流构建器。

Description:
    基于 LangGraph StateGraph 构建刊登工作流，
    支持商品导入、素材优化、文案生成、合规检查的并行执行。
    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → END
@author ganjianfei
@version 1.0.0
2026-04-25
"""

import logging
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.agents.listing_compliance_checker import ComplianceCheckerAgent
from src.graph.listing_state import ListingState
from src.models.listing import ListingProduct, Platform

logger = logging.getLogger(__name__)


class ListingWorkflow:
    """刊登工作流封装。

    工作流:
        START → ImportProduct → [AssetOptimizer | Copywriter] → ComplianceCheck → END

    Attributes:
        app: 编译后的 LangGraph 应用。
    """

    def __init__(self, settings: Any | None = None) -> None:
        """初始化工作流。

        Args:
            settings: 可选的配置对象，用于注入到 Agent。
        """
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

        self._builder.set_entry_point("import_product")
        self._builder.add_edge("import_product", "optimize_assets")
        self._builder.add_edge("import_product", "generate_copy")
        self._builder.add_edge("optimize_assets", "compliance_check")
        self._builder.add_edge("generate_copy", "compliance_check")
        self._builder.add_edge("compliance_check", END)

    async def _import_node(self, state: ListingState) -> dict:
        """商品导入节点。"""
        if state.product:
            return {
                "product": state.product,
                "current_step": "imported",
                "step_results": {"import": {"status": "success"}},
            }
        return {"error": "No product provided", "current_step": "import_failed"}

    async def _asset_optimize_node(self, state: ListingState) -> dict:
        """素材优化节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "asset_failed"}
        # Phase 1: placeholder, Phase 2 集成实际 AssetOptimizerAgent
        return {
            "asset_packages": state.asset_packages,
            "current_step": "assets_optimized",
            "step_results": {"assets": {"status": "pending"}},
        }

    async def _copy_node(self, state: ListingState) -> dict:
        """文案生成节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "copy_failed"}
        # Phase 1: placeholder, Phase 2 集成实际 CopywriterAgent
        return {
            "copywriting_packages": state.copywriting_packages,
            "current_step": "copy_generated",
            "step_results": {"copy": {"status": "pending"}},
        }

    async def _compliance_node(self, state: ListingState) -> dict:
        """合规检查节点。"""
        if not state.product:
            return {"error": "No product available", "current_step": "compliance_failed"}
        agent = ComplianceCheckerAgent(settings=self._settings)
        result = await agent.execute(state)
        return {
            "compliance_reports": result.get("compliance_reports", {}),
            "current_step": "compliance_checked",
            "step_results": {"compliance": {"status": "done"}},
        }

    async def run(
        self,
        product: ListingProduct,
        target_platforms: list[Platform],
        thread_id: str = "default",
    ) -> dict:
        """执行刊登工作流。

        Args:
            product: 待刊登商品。
            target_platforms: 目标平台列表。
            thread_id: 会话线程 ID，用于检查点。

        Returns:
            工作流最终状态。
        """
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = ListingState(
            product=product,
            target_platforms=target_platforms,
        )
        return await self.app.ainvoke(initial_state, config=config)
