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
from sqlalchemy import select

from src.agents.listing_asset_loader import ListingAssetLoader
from src.agents.listing_asset_optimizer import AssetOptimizerAgent
from src.agents.listing_compliance_checker import ComplianceCheckerAgent
from src.agents.listing_copywriter import AICopywritingAgent
from src.agents.listing_push_service import ListingPushService
from src.db.listing_models import ListingProductPO, ListingTaskPO
from src.db.postgres import get_db_session
from src.graph import listing_persistence
from src.graph.listing_state import ListingState
from src.models.listing import (
    ComplianceStatus,
    ImageRef,
    ListingProduct,
    ListingTask,
    Platform,
    TaskStatus,
)

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
        """构建状态图。

        拓扑:
            import_product ──(error)──▶ finalize
            import_product ──(ok)──▶ optimize_assets ─┐
                                      generate_copy ──┴─▶ compliance_check
            compliance_check ──(有阻断)──▶ finalize
            compliance_check ──(全通过)──▶ platform_push ──▶ finalize ──▶ END
        """
        self._builder.add_node("import_product", self._import_node)
        self._builder.add_node("optimize_assets", self._asset_optimize_node)
        self._builder.add_node("generate_copy", self._copy_node)
        self._builder.add_node("compliance_check", self._compliance_node)
        self._builder.add_node("platform_push", self._push_node)
        self._builder.add_node("finalize", self._finalize_node)

        self._builder.set_entry_point("import_product")
        self._builder.add_conditional_edges(
            "import_product",
            self._route_after_import,
            ["optimize_assets", "generate_copy", "finalize"],
        )
        self._builder.add_edge("optimize_assets", "compliance_check")
        self._builder.add_edge("generate_copy", "compliance_check")
        self._builder.add_conditional_edges(
            "compliance_check",
            self._route_after_compliance,
            ["platform_push", "finalize"],
        )
        self._builder.add_edge("platform_push", "finalize")
        self._builder.add_edge("finalize", END)

    @staticmethod
    def _route_after_import(state: ListingState) -> list[str]:
        """import 后路由：有致命错误直接进 finalize，否则并行生成素材与文案。"""
        if state.error:
            return ["finalize"]
        return ["optimize_assets", "generate_copy"]

    @staticmethod
    def _route_after_compliance(state: ListingState) -> list[str]:
        """合规门禁：任一平台 FAIL → 挂起人工审核（finalize，不推送）。"""
        if state.error:
            return ["finalize"]
        if state.blocked_platforms:
            return ["finalize"]
        return ["platform_push"]

    async def _finalize_node(self, state: ListingState) -> dict:
        """汇总工作流结果，计算并持久化任务终态。

        终态规则:
            - 有致命错误且无推送成功 → failed
            - 有合规阻断且未推送 → reviewing（挂起，等待人工审核）
            - 全部目标平台推送成功 → published
            - 部分推送成功 → partial
            - 其余（推送全部失败等）→ failed
        """
        push_results: dict[str, Any] = state.push_results or {}
        succeeded = {name for name, r in push_results.items() if r.success}
        target_names = {p.value for p in state.target_platforms}

        if state.error and not succeeded:
            final_status = TaskStatus.FAILED.value
        elif state.blocked_platforms and not push_results:
            final_status = TaskStatus.REVIEWING.value
        elif push_results:
            if target_names and succeeded >= target_names:
                final_status = TaskStatus.PUBLISHED.value
            elif succeeded:
                final_status = TaskStatus.PARTIAL.value
            else:
                final_status = TaskStatus.FAILED.value
        else:
            final_status = TaskStatus.FAILED.value

        logger.info(
            f"刊登工作流结束: task_id={state.task_id}, final={final_status}, "
            f"pushed={sorted(succeeded)}, blocked={[p.value for p in state.blocked_platforms]}"
        )

        if state.task_id is not None:
            await listing_persistence.update_task_status(
                state.task_id, state.tenant_id, final_status, workflow_state="finalized"
            )

        return {
            "current_step": "finalized",
            "step_results": {**state.step_results, "final_status": final_status},
        }

    async def _import_node(self, state: ListingState) -> dict:
        """商品导入节点。

        若商品 attributes 中包含 source_product_id，从 generated_assets
        表拉取 AI 生成图片填充到 source_images，实现视觉生成产物的复用。
        """
        if not state.product:
            return {
                "error": "No product provided",
                "errors": [{"node": "import_product", "error": "No product provided"}],
                "current_step": "import_failed",
            }

        product = state.product
        source_product_id = product.attributes.get("source_product_id")
        if source_product_id and not product.source_images:
            try:
                async with get_db_session() as session:
                    loader = ListingAssetLoader(session=session)
                    image_refs = await loader.load_images(
                        tenant_id=state.tenant_id,
                        product_id=source_product_id,
                    )
                if image_refs:
                    product.source_images = image_refs
                    logger.info(
                        f"商品 {product.sku} 加载 {len(image_refs)} 张 AI 生成图"
                    )
            except Exception as e:
                logger.error(f"加载 AI 生成图失败: {e}")
                return {
                    "product": product,
                    "errors": [{"node": "import_product", "error": str(e)}],
                    "current_step": "imported",
                }

        return {"product": product, "current_step": "imported"}

    async def _asset_optimize_node(self, state: ListingState) -> dict:
        """素材优化节点：调用 AssetOptimizerAgent。"""
        if not state.product:
            return {
                "errors": [
                    {"node": "optimize_assets", "error": "No product available"}
                ],
                "current_step": "optimize_skipped",
            }

        try:
            agent = AssetOptimizerAgent(settings=self._settings)
            result = agent.execute_sync(state)
            packages = result.get("asset_packages", state.asset_packages)
            if state.task_id is not None:
                await listing_persistence.save_asset_packages(
                    state.task_id, state.tenant_id, packages
                )
            return {
                "asset_packages": packages,
                "current_step": "assets_optimized",
            }
        except Exception as e:
            logger.exception(f"Asset optimization failed: {e}")
            return {
                "errors": [{"node": "optimize_assets", "error": str(e)}],
                "current_step": "optimize_failed",
            }

    async def _copy_node(self, state: ListingState) -> dict:
        """文案生成节点：调用 AICopywritingAgent（含 LLM）。"""
        if not state.product:
            return {
                "errors": [{"node": "generate_copy", "error": "No product available"}],
                "current_step": "copy_skipped",
            }

        try:
            agent = AICopywritingAgent(settings=self._settings)
            result = await agent.execute(state)
            packages = result.get("copywriting_packages", {})
            if state.task_id is not None:
                await listing_persistence.save_copywriting_packages(
                    state.task_id, state.tenant_id, packages
                )
            return {
                "copywriting_packages": packages,
                "current_step": "copy_generated",
            }
        except Exception as e:
            logger.exception(f"Copywriting generation failed: {e}")
            return {
                "errors": [{"node": "generate_copy", "error": str(e)}],
                "current_step": "copy_failed",
            }

    async def _compliance_node(self, state: ListingState) -> dict:
        """合规检查节点：输出报告并标记被阻断平台。"""
        if not state.product:
            return {
                "errors": [
                    {"node": "compliance_check", "error": "No product available"}
                ],
                "current_step": "compliance_failed",
            }
        agent = ComplianceCheckerAgent(settings=self._settings)
        result = agent.execute_sync(state)
        reports = result.get("compliance_reports", {})
        blocked = [p for p, r in reports.items() if r.overall == ComplianceStatus.FAIL]
        if blocked:
            logger.warning(
                f"合规阻断平台: {[p.value for p in blocked]}，任务挂起等待人工审核"
            )
        if state.task_id is not None:
            await listing_persistence.save_compliance_reports(
                state.task_id, state.tenant_id, reports
            )
        return {
            "compliance_reports": reports,
            "blocked_platforms": blocked,
            "current_step": "compliance_checked",
        }

    async def _push_with_retry(
        self,
        *,
        product: ListingProduct,
        asset_packages: dict[Platform, Any],
        copywriting_packages: dict[Platform, Any],
        platforms: list[Platform],
        task_id: int | None,
        tenant_id: str,
    ) -> dict[str, Any]:
        """推送指定平台：失败后自动重试一次非永久错误，并按需持久化结果。

        Args:
            product: 源商品。
            asset_packages: 各平台素材包。
            copywriting_packages: 各平台文案包。
            platforms: 本次要推送的平台。
            task_id: 关联任务 ID（None 时跳过持久化）。
            tenant_id: 租户 ID。

        Returns:
            各平台推送结果 {platform_name: PushResult}。
        """
        push_service = ListingPushService()
        task = ListingTask(
            id=task_id,
            product_id=product.id or 0,
            target_platforms=platforms,
            status=TaskStatus.PUSHING,
        )

        results = await push_service.push_to_platforms(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            task=task,
        )

        # 对非永久性错误自动重试一次（retry_failed 内部排除 PERMANENT_ERROR）
        if any(not r.success for r in results.values()):
            failed_names = [n for n, r in results.items() if not r.success]
            logger.info(f"推送失败平台 {failed_names}，自动重试一次")
            results = await push_service.retry_failed(
                product=product,
                asset_packages=asset_packages,
                copywriting_packages=copywriting_packages,
                task=task,
                previous_results=results,
            )

        if task_id is not None:
            await listing_persistence.save_push_results(task_id, tenant_id, results)

        return results

    async def _push_node(self, state: ListingState) -> dict:
        """平台推送节点：并行推送到未被阻断的平台。"""
        if not state.product:
            return {
                "errors": [{"node": "platform_push", "error": "No product available"}],
                "current_step": "push_failed",
            }

        # 防御：被阻断平台不推送（正常路由不会到达此分支）
        push_platforms = [
            p for p in state.target_platforms if p not in state.blocked_platforms
        ]
        if not push_platforms:
            return {"current_step": "push_skipped"}

        if state.task_id is not None:
            await listing_persistence.update_task_status(
                state.task_id,
                state.tenant_id,
                TaskStatus.PUSHING.value,
                workflow_state="platform_push",
            )

        try:
            push_results = await self._push_with_retry(
                product=state.product,
                asset_packages=state.asset_packages,
                copywriting_packages=state.copywriting_packages,
                platforms=push_platforms,
                task_id=state.task_id,
                tenant_id=state.tenant_id,
            )
            return {"push_results": push_results, "current_step": "push_executed"}
        except Exception as e:
            logger.exception(f"Platform push failed: {e}")
            return {
                "errors": [{"node": "platform_push", "error": str(e)}],
                "current_step": "push_failed",
            }

    async def run(
        self,
        product: ListingProduct | None,
        target_platforms: list[Platform],
        thread_id: str = "default",
        task_id: int | None = None,
        tenant_id: str = "",
    ) -> dict:
        """执行刊登工作流。

        Args:
            product: 标准化商品；None 时走 import 失败快速终止。
            target_platforms: 目标平台。
            thread_id: LangGraph 会话 ID。
            task_id: 关联刊登任务 ID；提供时各阶段产物与任务状态持久化。
            tenant_id: 租户 ID（持久化与资产加载的租户隔离）。
        """
        if task_id is not None:
            await listing_persistence.update_task_status(
                task_id, tenant_id, TaskStatus.GENERATING.value,
                workflow_state="import_product",
            )
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = ListingState(
            product=product,
            target_platforms=target_platforms,
            task_id=task_id,
            tenant_id=tenant_id,
        )
        return await self.app.ainvoke(initial_state, config=config)

    async def resume_push(
        self,
        *,
        task_id: int,
        tenant_id: str,
        platforms: list[Platform],
    ) -> dict[str, Any]:
        """人工审核后恢复推送。

        从数据库加载商品、素材包、文案包，仅推送指定平台
        （显式列出的合规 FAIL 平台视为人工确认放行）。
        终态按任务累计推送结果计算：
            全部目标平台成功 → published；部分成功 → partial；
            全部失败 → reviewing（保持挂起，可再次恢复）。

        Args:
            task_id: 刊登任务 ID。
            tenant_id: 租户 ID。
            platforms: 本次要推送的平台（须为目标平台子集）。

        Returns:
            {"push_results": dict[str, PushResult], "final_status": str}

        Raises:
            ValueError: 任务/商品不存在、租户不匹配或无可推送平台。
        """
        async with get_db_session() as session:
            task_po = await session.get(ListingTaskPO, task_id)
            if not task_po or task_po.tenant_id != tenant_id:
                raise ValueError(f"刊登任务 {task_id} 不存在")
            target = [Platform(p) for p in task_po.target_platforms]
            result = await session.execute(
                select(ListingProductPO).where(
                    ListingProductPO.sku == task_po.product_sku,
                    ListingProductPO.tenant_id == tenant_id,
                )
            )
            product_po = result.scalar_one_or_none()
            if not product_po:
                raise ValueError(f"商品 {task_po.product_sku} 不存在")

        push_set = [p for p in platforms if p in target]
        if not push_set:
            raise ValueError("无可推送平台：所申请平台均不在任务目标平台内")

        product = ListingProduct(
            id=product_po.id,
            sku=product_po.sku,
            title=product_po.title,
            description=product_po.description,
            category=product_po.category,
            brand=product_po.brand,
            source_images=[ImageRef(**img) for img in (product_po.source_images or [])],
            attributes=product_po.attributes or {},
        )
        asset_packages = await listing_persistence.load_asset_packages(
            task_id, tenant_id
        )
        copywriting_packages = await listing_persistence.load_copywriting_packages(
            task_id, tenant_id
        )

        await listing_persistence.update_task_status(
            task_id, tenant_id, TaskStatus.PUSHING.value, workflow_state="resume_push"
        )

        results = await self._push_with_retry(
            product=product,
            asset_packages=asset_packages,
            copywriting_packages=copywriting_packages,
            platforms=push_set,
            task_id=task_id,
            tenant_id=tenant_id,
        )

        # 终态基于任务累计推送结果（含历史成功）
        statuses = await listing_persistence.load_push_result_statuses(
            task_id, tenant_id
        )
        succeeded = {name for name, ok in statuses.items() if ok}
        target_names = {p.value for p in target}
        if succeeded >= target_names:
            final_status = TaskStatus.PUBLISHED.value
        elif succeeded:
            final_status = TaskStatus.PARTIAL.value
        else:
            final_status = TaskStatus.REVIEWING.value

        await listing_persistence.update_task_status(
            task_id, tenant_id, final_status, workflow_state="resume_push_done"
        )

        logger.info(
            f"恢复推送完成: task_id={task_id}, final={final_status}, "
            f"pushed={sorted(succeeded)}"
        )
        return {"push_results": results, "final_status": final_status}
