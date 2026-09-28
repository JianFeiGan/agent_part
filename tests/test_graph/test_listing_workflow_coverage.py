"""
视觉生成工作流与刊登工作流覆盖率补齐测试。

Description:
    补齐 src/graph/workflow.py 的路由分支、make_agent_node 失败/成功路径、
    RAG 依赖注入分支、ProductVisualWorkflow 生命周期行为，
    以及 src/graph/listing_workflow.py 的异常路径与部分成功终态判定。
    全部通过 mock 隔离外部依赖，不发起真实调用。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentResult
from src.agents.listing_platform_adapter import PushResult
from src.graph.listing_state import ListingState
from src.graph.listing_workflow import ListingWorkflow
from src.graph.state import AgentState, GenerationRequest
from src.graph.workflow import (
    ProductVisualWorkflow,
    WorkflowBuilder,
    create_agent_log,
    create_workflow,
    make_agent_node,
    route_after_design,
    route_after_image_generation,
)
from src.models.listing import ListingProduct, Platform, TaskStatus
from src.models.product import Product, ProductCategory

# ==================== 路由分支 ====================


class TestRouteBranches:
    """工作流条件路由的边界分支测试。"""

    def test_route_after_image_generation_without_request(self) -> None:
        """generation_request 为 None 时应直接进入质量审核。"""
        state = AgentState()
        assert route_after_image_generation(state) == "quality_reviewer"

    def test_route_after_design_without_request(self) -> None:
        """generation_request 为 None 时 route_after_design 应结束。"""
        state = AgentState()
        assert route_after_design(state) == "end"

    def test_route_after_design_image_only(self) -> None:
        """image_only 任务应路由到 image_generator。"""
        state = AgentState(generation_request=GenerationRequest(task_type="image_only"))
        assert route_after_design(state) == "image_generator"

    def test_route_after_design_video_only(self) -> None:
        """video_only 任务应路由到 video_generator。"""
        state = AgentState(generation_request=GenerationRequest(task_type="video_only"))
        assert route_after_design(state) == "video_generator"

    def test_route_after_image_generation_image_and_video(self) -> None:
        """image_and_video 任务图片生成后必须进视频生成。"""
        state = AgentState(generation_request=GenerationRequest(task_type="image_and_video"))
        assert route_after_image_generation(state) == "video_generator"

    def test_create_agent_log_non_running_status(self) -> None:
        """非 running 状态的 AgentLog 不应记录 start_time。"""
        log = create_agent_log("orchestrator", "completed")
        assert log.start_time is None
        assert log.status == "completed"


# ==================== make_agent_node ====================


class TestMakeAgentNode:
    """make_agent_node 节点函数的成功/失败/Trace 路径测试。"""

    @staticmethod
    def _make_state() -> AgentState:
        """创建测试用初始状态。"""
        return AgentState(
            generation_request=GenerationRequest(),
            selling_points=[{"point": "a"}],
            completed_steps=["orchestration"],
        )

    @pytest.mark.asyncio
    async def test_failure_path_records_error_and_snapshots(self) -> None:
        """Agent 失败时应写入 error 并保留 input_snapshot。"""
        agent = AsyncMock()
        agent.execute = AsyncMock(return_value=AgentResult(success=False, error="boom"))
        node = make_agent_node(
            "requirement_analyzer",
            "requirement_analysis",
            agent,
            lambda _r: {"selling_points": []},
            summarize="done",
            input_snapshot=lambda _s: {"product_info": "x"},
        )
        result = await node(self._make_state())
        assert result["error"] == "boom"
        assert result["current_step"] == "requirement_analysis"
        log = result["agent_logs"][0]
        assert log.status == "failed"
        assert log.input_data == {"product_info": "x"}

    @pytest.mark.asyncio
    async def test_failure_path_without_snapshots(self) -> None:
        """未提供 snapshot 回调时失败路径不应崩溃。"""
        agent = AsyncMock()
        agent.execute = AsyncMock(return_value=AgentResult(success=False, error=None))
        node = make_agent_node(
            "video_generator",
            "video_generation",
            agent,
            lambda _r: {},
            apply_trace=False,
        )
        result = await node(self._make_state())
        assert result["error"] is None
        log = result["agent_logs"][0]
        assert log.message == "执行失败"

    @pytest.mark.asyncio
    async def test_success_path_applies_trace_and_snapshots(self) -> None:
        """成功路径应回写 Trace、input/output snapshot 并累加 completed_steps。"""
        agent = MagicMock()
        agent._last_trace = {
            "prompt_template": "tpl",
            "prompt_variables": {"v": 1},
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost_cny": 0.01,
            "latency_ms": 123,
            "model_name": "qwen",
            "provider": "dashscope",
        }
        agent.execute = AsyncMock(
            return_value=AgentResult(
                success=True, data={"requirement_report": {"key_features": ["f1"]}}
            )
        )
        node = make_agent_node(
            "requirement_analyzer",
            "requirement_analysis",
            agent,
            lambda r: {"requirement_report": r.data.get("requirement_report")},
            summarize=lambda r: f"分析完成，发现 {len(r.data.get('selling_points', []))} 个卖点",
            input_snapshot=lambda _s: {"product_info": "p"},
            output_snapshot=lambda _r: {"selling_points_count": 0},
        )
        state = self._make_state()
        result = await node(state)
        assert result["current_step"] == "requirement_analysis"
        assert result["requirement_report"] == {"key_features": ["f1"]}
        assert result["completed_steps"] == ["orchestration", "requirement_analysis"]
        log = result["agent_logs"][0]
        assert log.status == "completed"
        assert log.prompt_template == "tpl"
        assert log.input_tokens == 10
        assert log.output_tokens == 5
        assert log.total_tokens == 15
        assert log.model_name == "qwen"
        assert log.provider == "dashscope"
        assert log.input_data == {"product_info": "p"}
        assert log.output_data == {"selling_points_count": 0}

    @pytest.mark.asyncio
    async def test_success_path_without_trace(self) -> None:
        """Agent 无 _last_trace 时成功路径不应崩溃。"""
        agent = MagicMock(spec=[])  # 无 _last_trace 属性
        agent.execute = AsyncMock(return_value=AgentResult(success=True, data={}))
        node = make_agent_node(
            "orchestrator",
            "orchestration",
            agent,
            lambda _r: {},
            apply_trace=True,
            summarize="编排调度完成",
        )
        result = await node(self._make_state())
        assert result["current_step"] == "orchestration"
        log = result["agent_logs"][0]
        assert log.status == "completed"
        assert log.output_summary == "编排调度完成"


# ==================== WorkflowBuilder ====================


class TestWorkflowBuilderRagBranches:
    """WorkflowBuilder RAG 依赖注入分支测试。"""

    def test_set_rag_dependencies_sets_fields(self) -> None:
        """set_rag_dependencies 应更新 retriever 与 session。"""
        builder = WorkflowBuilder(rag_enabled=True)
        retriever = MagicMock()
        session = MagicMock()
        result = builder.set_rag_dependencies(retriever=retriever, session=session)
        assert result is builder
        assert builder._retriever is retriever
        assert builder._session is session

    def test_set_rag_dependencies_keeps_existing_on_none(self) -> None:
        """传 None 时不覆盖已有依赖。"""
        retriever = MagicMock()
        builder = WorkflowBuilder(retriever=retriever, rag_enabled=True)
        builder.set_rag_dependencies()
        assert builder._retriever is retriever

    def test_create_creative_planner_uses_rag_variant(self) -> None:
        """有 retriever 且 rag_enabled 时应创建 RAG 增强版创意策划 Agent。"""
        builder = WorkflowBuilder(retriever=MagicMock(), rag_enabled=True)
        agent = builder._create_creative_planner()
        from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner

        assert isinstance(agent, RAGEnhancedCreativePlanner)

    def test_create_creative_planner_without_rag(self) -> None:
        """无 retriever 时应创建普通创意策划 Agent。"""
        builder = WorkflowBuilder(retriever=None, rag_enabled=True)
        agent = builder._create_creative_planner()
        from src.agents.creative_planner import CreativePlannerAgent

        assert isinstance(agent, CreativePlannerAgent)

    def test_create_quality_reviewer_uses_rag_variant(self) -> None:
        """有 retriever 且 rag_enabled 时应创建 RAG 增强版质量审核 Agent。"""
        builder = WorkflowBuilder(retriever=MagicMock(), rag_enabled=True)
        agent = builder._create_quality_reviewer()
        from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer

        assert isinstance(agent, RAGEnhancedQualityReviewer)

    def test_create_quality_reviewer_without_rag(self) -> None:
        """rag_enabled=False 时应创建普通质量审核 Agent。"""
        builder = WorkflowBuilder(retriever=MagicMock(), rag_enabled=False)
        agent = builder._create_quality_reviewer()
        from src.agents.quality_reviewer import QualityReviewerAgent

        assert isinstance(agent, QualityReviewerAgent)

    def test_create_image_generator_without_rag(self) -> None:
        """无 retriever 时应创建普通图片生成 Agent。"""
        builder = WorkflowBuilder(retriever=None, rag_enabled=True)
        agent = builder._create_image_generator()
        from src.agents.image_generator import ImageGeneratorAgent

        assert isinstance(agent, ImageGeneratorAgent)

    def test_add_edges_requires_nodes(self) -> None:
        """未添加节点时 add_edges 应抛 RuntimeError。"""
        builder = WorkflowBuilder()
        with pytest.raises(RuntimeError, match="add_agent_nodes"):
            builder.add_edges()

    def test_compile_requires_full_build(self) -> None:
        """未完成构建时 compile 应抛 RuntimeError。"""
        builder = WorkflowBuilder()
        with pytest.raises(RuntimeError, match="add_agent_nodes"):
            builder.compile()


# ==================== create_workflow / ProductVisualWorkflow ====================


class TestCreateWorkflow:
    """create_workflow 与 ProductVisualWorkflow 生命周期测试。"""

    def test_create_workflow_returns_compiled_graph(self) -> None:
        """create_workflow 应返回可执行的编译图。"""
        app = create_workflow(rag_enabled=False)
        assert app is not None
        assert hasattr(app, "ainvoke")

    @pytest.mark.asyncio
    async def test_run_converts_dict_result_to_state(self) -> None:
        """run 返回 dict 时应转换为 AgentState。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        fake_state = {"current_step": "done", "error": None}
        workflow.app = MagicMock()
        workflow.app.ainvoke = AsyncMock(return_value=fake_state)
        product = Product(
            name="test product",
            category=ProductCategory.DIGITAL,
            description="A test product description for coverage.",
        )
        result = await workflow.run(product, thread_id="t1")
        assert isinstance(result, AgentState)
        assert result.current_step == "done"
        workflow.app.ainvoke.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_accepts_agent_state_result(self) -> None:
        """run 返回 AgentState 时应原样返回。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        state = AgentState(current_step="done")
        workflow.app = MagicMock()
        workflow.app.ainvoke = AsyncMock(return_value=state)
        product = Product(
            name="test product",
            category=ProductCategory.DIGITAL,
            description="A test product description for coverage.",
        )
        result = await workflow.run(product)
        assert result is state

    @pytest.mark.asyncio
    async def test_get_state_returns_none_when_empty(self) -> None:
        """状态为空时 get_state 应返回 None。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        workflow.app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {}
        workflow.app.aget_state = AsyncMock(return_value=snapshot)
        result = await workflow.get_state("t1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_state_converts_dict_values(self) -> None:
        """状态值为 dict 时应转换为 AgentState。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        workflow.app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = {"current_step": "analysis"}
        workflow.app.aget_state = AsyncMock(return_value=snapshot)
        result = await workflow.get_state("t1")
        assert isinstance(result, AgentState)
        assert result.current_step == "analysis"

    @pytest.mark.asyncio
    async def test_get_state_accepts_agent_state_values(self) -> None:
        """状态值为 AgentState 时应原样返回。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        state = AgentState(current_step="x")
        workflow.app = MagicMock()
        snapshot = MagicMock()
        snapshot.values = state
        workflow.app.aget_state = AsyncMock(return_value=snapshot)
        result = await workflow.get_state("t1")
        assert result is state

    def test_set_session_recreates_workflow(self) -> None:
        """set_session 应重建 app 以注入新 session。"""
        workflow = ProductVisualWorkflow(rag_enabled=False)
        old_app = workflow.app
        session = MagicMock()
        workflow.set_session(session)
        assert workflow.app is not old_app
        assert workflow._session is session


# ==================== 刊登工作流：异常与部分成功终态 ====================


def _make_product() -> ListingProduct:
    """创建刊登测试商品。"""
    return ListingProduct(sku="WF-SKU-1", title="Workflow Test", description="d")


def _push_result(success: bool, platform: Platform = Platform.AMAZON) -> PushResult:
    """创建 PushResult 测试替身。"""
    return PushResult(success=success, platform=platform, listing_id="L1" if success else None)


class TestListingWorkflowExceptionPaths:
    """刊登工作流各节点异常/空输入路径测试。"""

    @pytest.mark.asyncio
    async def test_compliance_route_with_error_goes_to_finalize(self) -> None:
        """合规阶段已有 error 时应路由到 finalize。"""
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON],
            error="something broke",
        )
        assert ListingWorkflow._route_after_compliance(state) == ["finalize"]

    @pytest.mark.asyncio
    async def test_finalize_partial_success_gives_partial(self) -> None:
        """部分平台成功时终态应为 partial（刊登任务特有）。"""
        workflow = ListingWorkflow()
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON, Platform.EBAY],
            push_results={
                "amazon": _push_result(True, Platform.AMAZON),
                "ebay": _push_result(False, Platform.EBAY),
            },
        )
        with patch(
            "src.graph.listing_workflow.listing_persistence.update_task_status",
            new=AsyncMock(),
        ):
            result = await workflow._finalize_node(state)
        assert result["step_results"]["final_status"] == TaskStatus.PARTIAL.value

    @pytest.mark.asyncio
    async def test_finalize_no_results_no_error_gives_failed(self) -> None:
        """无推送结果且无阻断/错误时终态应为 failed。"""
        workflow = ListingWorkflow()
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON],
        )
        with patch(
            "src.graph.listing_workflow.listing_persistence.update_task_status",
            new=AsyncMock(),
        ):
            result = await workflow._finalize_node(state)
        assert result["step_results"]["final_status"] == TaskStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_asset_optimize_without_product_skips(self) -> None:
        """无商品时素材优化应跳过。"""
        workflow = ListingWorkflow()
        state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await workflow._asset_optimize_node(state)
        assert result["current_step"] == "optimize_skipped"
        assert result["errors"][0]["node"] == "optimize_assets"

    @pytest.mark.asyncio
    async def test_copy_node_without_product_skips(self) -> None:
        """无商品时文案生成应跳过。"""
        workflow = ListingWorkflow()
        state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await workflow._copy_node(state)
        assert result["current_step"] == "copy_skipped"

    @pytest.mark.asyncio
    async def test_compliance_without_product_fails(self) -> None:
        """无商品时合规检查应记录错误。"""
        workflow = ListingWorkflow()
        state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await workflow._compliance_node(state)
        assert result["current_step"] == "compliance_failed"

    @pytest.mark.asyncio
    async def test_push_without_product_fails(self) -> None:
        """无商品时平台推送应记录错误。"""
        workflow = ListingWorkflow()
        state = ListingState(product=None, target_platforms=[Platform.AMAZON])
        result = await workflow._push_node(state)
        assert result["current_step"] == "push_failed"

    @pytest.mark.asyncio
    async def test_push_skipped_when_all_platforms_blocked(self) -> None:
        """所有平台被阻断时推送应跳过。"""
        workflow = ListingWorkflow()
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON],
            blocked_platforms=[Platform.AMAZON],
        )
        result = await workflow._push_node(state)
        assert result["current_step"] == "push_skipped"

    @pytest.mark.asyncio
    async def test_push_exception_records_error(self) -> None:
        """推送内部异常应被记录为节点错误。"""
        workflow = ListingWorkflow()
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON],
        )
        with patch.object(
            ListingWorkflow,
            "_push_with_retry",
            new=AsyncMock(side_effect=RuntimeError("push exploded")),
        ):
            result = await workflow._push_node(state)
        assert result["current_step"] == "push_failed"
        assert "push exploded" in result["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_copy_node_exception_records_error(self) -> None:
        """文案生成内部异常应被记录为节点错误。"""
        workflow = ListingWorkflow()
        state = ListingState(
            product=_make_product(),
            target_platforms=[Platform.AMAZON],
        )
        with patch("src.graph.listing_workflow.AICopywritingAgent") as mock_cls:
            mock_cls.return_value.execute = AsyncMock(side_effect=RuntimeError("llm down"))
            result = await workflow._copy_node(state)
        assert result["current_step"] == "copy_failed"
        assert "llm down" in result["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_import_node_load_failure_records_error(self) -> None:
        """AI 图片加载失败时应记录错误但不中断 import。"""
        workflow = ListingWorkflow()
        product = ListingProduct(
            sku="WF-SKU-2",
            title="With Source",
            attributes={"source_product_id": 99},
        )
        state = ListingState(product=product, target_platforms=[Platform.AMAZON])
        with patch("src.graph.listing_workflow.get_db_session") as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with patch("src.graph.listing_workflow.ListingAssetLoader") as mock_loader_cls:
                mock_loader_cls.return_value.load_images = AsyncMock(
                    side_effect=RuntimeError("db down")
                )
                result = await workflow._import_node(state)
        assert result["current_step"] == "imported"
        assert "db down" in result["errors"][0]["error"]


class TestListingWorkflowResumePartial:
    """resume_push 部分成功终态判定测试。"""

    @pytest.mark.asyncio
    async def test_resume_push_partial_gives_partial(self) -> None:
        """恢复推送后累计部分成功应判定为 partial。"""
        workflow = ListingWorkflow()
        task_po = MagicMock()
        task_po.tenant_id = "t1"
        task_po.target_platforms = ["amazon", "ebay"]
        task_po.product_sku = "WF-SKU-1"
        product_po = MagicMock()
        product_po.id = 1
        product_po.sku = "WF-SKU-1"
        product_po.title = "T"
        product_po.description = "d"
        product_po.category = None
        product_po.brand = None
        product_po.source_images = []
        product_po.attributes = {}

        session = AsyncMock()
        session.get = AsyncMock(return_value=task_po)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=product_po)
        session.execute = AsyncMock(return_value=execute_result)

        with patch("src.graph.listing_workflow.get_db_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with (
                patch(
                    "src.graph.listing_workflow.listing_persistence.load_asset_packages",
                    new=AsyncMock(return_value=[]),
                ),
                patch(
                    "src.graph.listing_workflow.listing_persistence.load_copywriting_packages",
                    new=AsyncMock(return_value={}),
                ),
                patch(
                    "src.graph.listing_workflow.listing_persistence.load_push_result_statuses",
                    new=AsyncMock(return_value={"amazon": True, "ebay": False}),
                ),
                patch(
                    "src.graph.listing_workflow.listing_persistence.update_task_status",
                    new=AsyncMock(),
                ),
                patch.object(
                    ListingWorkflow,
                    "_push_with_retry",
                    new=AsyncMock(return_value={"amazon": _push_result(True)}),
                ),
            ):
                result = await workflow.resume_push(
                    task_id=1,
                    tenant_id="t1",
                    platforms=[Platform.AMAZON, Platform.EBAY],
                )
        assert result["final_status"] == TaskStatus.PARTIAL.value

    @pytest.mark.asyncio
    async def test_resume_push_product_not_found_raises(self) -> None:
        """商品不存在时 resume_push 应抛 ValueError。"""
        workflow = ListingWorkflow()
        task_po = MagicMock()
        task_po.tenant_id = "t1"
        task_po.target_platforms = ["amazon"]
        task_po.product_sku = "GONE"

        session = AsyncMock()
        session.get = AsyncMock(return_value=task_po)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=execute_result)

        with patch("src.graph.listing_workflow.get_db_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="不存在"):
                await workflow.resume_push(
                    task_id=1,
                    tenant_id="t1",
                    platforms=[Platform.AMAZON],
                )

    @pytest.mark.asyncio
    async def test_resume_push_no_matching_platforms_raises(self) -> None:
        """所申请平台均不在目标平台内时应抛 ValueError。"""
        workflow = ListingWorkflow()
        task_po = MagicMock()
        task_po.tenant_id = "t1"
        task_po.target_platforms = ["amazon"]
        task_po.product_sku = "WF-SKU-1"
        product_po = MagicMock()
        product_po.id = 1
        product_po.sku = "WF-SKU-1"
        product_po.title = "T"
        product_po.description = "d"
        product_po.category = None
        product_po.brand = None
        product_po.source_images = []
        product_po.attributes = {}

        session = AsyncMock()
        session.get = AsyncMock(return_value=task_po)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=product_po)
        session.execute = AsyncMock(return_value=execute_result)

        with patch("src.graph.listing_workflow.get_db_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(ValueError, match="无可推送平台"):
                await workflow.resume_push(
                    task_id=1,
                    tenant_id="t1",
                    platforms=[Platform.SHOPIFY],
                )
