"""
视觉生成工作流与刊登工作流覆盖率补齐测试。

Description:
    补齐 src/graph/workflow.py 的路由分支、make_agent_node 失败/成功路径、
    Trace 经公开 invoke_llm 产生并回写日志、WorkflowBuilder 各 RAG 配置下的
    公开构建链路，以及 src/graph/listing_workflow.py 经 run/resume_push
    公开入口的异常路径与部分成功终态判定。
    全部通过 mock 隔离外部依赖，不发起真实调用。
@author ganjianfei
@version 1.1.0
2026-10-24
"""

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import AgentResult
from src.agents.listing_platform_adapter import PushResult
from src.agents.requirement_analyzer import RequirementAnalyzerAgent
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
from src.models.listing import (
    ComplianceReport,
    ComplianceStatus,
    ListingProduct,
    Platform,
    TaskStatus,
)
from src.models.product import Product, ProductCategory


class _StubChatModel(BaseChatModel):
    """最小聊天模型替身：固定回复，model_name 可断言。"""

    model_name: str = "stub-chat-model"

    @property
    def _llm_type(self) -> str:
        """LangChain 模型类型标识。"""
        return "stub-chat-model"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """返回固定回复。"""
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


class _FakeRecorder:
    """ConversationRecorder 替身：提供固定 token 计数，不触碰数据库。"""

    _input_tokens = 10
    _output_tokens = 5
    _start_time: float | None = None

    def __init__(self, **kwargs: Any) -> None:
        """接受与真实记录器一致的构造参数。"""

    async def __aenter__(self) -> "_FakeRecorder":
        """进入上下文。"""
        return self

    async def __aexit__(self, *exc_info: Any) -> bool:
        """退出上下文，不抑制异常。"""
        return False

    def set_response(self, response: Any) -> None:
        """记录响应（no-op）。"""


def _make_agent_with_stub_llm() -> RequirementAnalyzerAgent:
    """构造带 LLM 替身与配置替身的真实 Agent。"""
    settings = MagicMock()
    settings.llm_provider = "stub"
    settings.llm_retry_attempts = 0
    settings.llm_retry_initial_backoff = 0.0
    return RequirementAnalyzerAgent(llm=_StubChatModel(), settings=settings)


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
        agent = MagicMock()
        agent.execute = AsyncMock(return_value=AgentResult(success=False, error="boom"))
        node = make_agent_node(
            "requirement_analyzer",
            "requirement_analysis",
            agent,
            lambda _r: {"selling_points": []},
            apply_trace=False,
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
    async def test_failure_without_error_still_marks_failed(self) -> None:
        """Agent 失败且未携带错误信息时，日志仍应标记失败并记录结束时间。"""
        agent = MagicMock()
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
        assert log.status == "failed"
        assert log.end_time is not None

    @pytest.mark.asyncio
    async def test_success_path_applies_trace_and_snapshots(self) -> None:
        """成功路径应回写 Trace、input/output snapshot 并累加 completed_steps。

        Trace 数据经公开入口产生：真实 Agent 用替身 LLM 走一次 invoke_llm。
        """
        agent = _make_agent_with_stub_llm()
        prompt = ChatPromptTemplate.from_template("分析商品 {name}")
        with patch("src.api.service.conversation_recorder.ConversationRecorder", _FakeRecorder):
            await agent.invoke_llm(prompt, {"name": "智能手表"})
        agent.execute = AsyncMock(  # type: ignore[method-assign]
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
        assert log.prompt_template is not None
        assert "分析商品" in (log.prompt_template or "")
        assert log.input_tokens == 10
        assert log.output_tokens == 5
        assert log.total_tokens == 15
        assert log.model_name == "stub-chat-model"
        assert log.provider == "stub"
        assert log.cost_cny is not None and log.cost_cny >= 0
        assert log.input_data == {"product_info": "p"}
        assert log.output_data == {"selling_points_count": 0}

    @pytest.mark.asyncio
    async def test_success_path_without_llm_call_has_no_trace(self) -> None:
        """Agent 未调用过 LLM 时，成功日志不应携带 Trace 数据。"""
        agent = _make_agent_with_stub_llm()
        agent.execute = AsyncMock(  # type: ignore[method-assign]
            return_value=AgentResult(success=True, data={})
        )
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
        assert log.model_name is None
        assert log.total_tokens == 0


# ==================== WorkflowBuilder ====================


class TestWorkflowBuilderRagBranches:
    """WorkflowBuilder 各 RAG 配置下公开构建链路测试。"""

    def test_set_rag_dependencies_returns_builder_for_chaining(self) -> None:
        """set_rag_dependencies 应返回 self 并支持后续公开构建链路。"""
        builder = WorkflowBuilder(rag_enabled=True)
        result = builder.set_rag_dependencies(retriever=MagicMock(), session=MagicMock())
        assert result is builder
        app = result.add_agent_nodes().add_edges().compile()
        assert hasattr(app, "ainvoke")

    def test_set_rag_dependencies_keeps_existing_on_none(self) -> None:
        """传 None 时不覆盖已有依赖，构建链路仍可完成。"""
        builder = WorkflowBuilder(retriever=MagicMock(), rag_enabled=True)
        builder.set_rag_dependencies()
        app = builder.add_agent_nodes().add_edges().compile()
        assert hasattr(app, "ainvoke")

    def test_compile_with_rag_variants(self) -> None:
        """配置检索器且启用 RAG 时应能编译出完整工作流（RAG 增强变体注入）。"""
        app = create_workflow(retriever=MagicMock(), rag_enabled=True)
        assert app is not None
        assert hasattr(app, "ainvoke")

    def test_compile_without_retriever(self) -> None:
        """无检索器时应能编译出完整工作流（普通 Agent 注入）。"""
        app = create_workflow(retriever=None, rag_enabled=True)
        assert hasattr(app, "ainvoke")

    def test_compile_with_rag_disabled(self) -> None:
        """rag_enabled=False 时应能编译出完整工作流。"""
        app = create_workflow(retriever=MagicMock(), rag_enabled=False)
        assert hasattr(app, "ainvoke")

    def test_compile_rag_image_generator_when_image_rag_enabled(self) -> None:
        """image_rag_enabled 开启时 RAG 工作流应能编译（图片生成 RAG 变体注入）。"""
        settings = MagicMock()
        settings.image_rag_enabled = True
        with patch("src.graph.workflow.get_settings", return_value=settings):
            app = create_workflow(retriever=MagicMock(), rag_enabled=True)
        assert hasattr(app, "ainvoke")

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
        workflow.set_session(MagicMock())
        assert workflow.app is not old_app


# ==================== 刊登工作流：经公开入口 run/resume_push 的异常与终态 ====================


def _make_product() -> ListingProduct:
    """创建刊登测试商品。"""
    return ListingProduct(sku="WF-SKU-1", title="Workflow Test", description="d")


def _push_result(success: bool, platform: Platform = Platform.AMAZON) -> PushResult:
    """创建 PushResult 测试替身。"""
    return PushResult(success=success, platform=platform, listing_id="L1" if success else None)


def _benign_agents() -> dict[str, MagicMock]:
    """构造全链路放行的 Agent 协作者替身（素材/文案/合规）。"""
    optimizer = MagicMock()
    optimizer.return_value.execute_sync = MagicMock(return_value={"asset_packages": {}})
    copywriter = MagicMock()
    copywriter.return_value.execute = AsyncMock(return_value={"copywriting_packages": {}})
    compliance = MagicMock()
    compliance.return_value.execute_sync = MagicMock(return_value={"compliance_reports": {}})
    return {
        "src.graph.listing_workflow.AssetOptimizerAgent": optimizer,
        "src.graph.listing_workflow.AICopywritingAgent": copywriter,
        "src.graph.listing_workflow.ComplianceCheckerAgent": compliance,
    }


def _push_service(
    results: dict[str, PushResult] | None = None,
    error: Exception | None = None,
) -> MagicMock:
    """构造推送服务替身。"""
    service = MagicMock()
    if error is not None:
        service.return_value.push_to_platforms = AsyncMock(side_effect=error)
        service.return_value.retry_failed = AsyncMock(side_effect=error)
    else:
        service.return_value.push_to_platforms = AsyncMock(return_value=results or {})
        service.return_value.retry_failed = AsyncMock(return_value=results or {})
    return service


def _pipeline(extra: dict[str, Any] | None = None) -> ExitStack:
    """进入刊登工作流全链路替身上下文。

    隔离素材/文案/合规 Agent（可选覆盖）、推送服务与全部持久化写入；
    返回的 ExitStack 需以 with 语句使用。
    """
    agents = _benign_agents()
    if extra:
        agents.update(extra)
    stack = ExitStack()
    stack.enter_context(
        patch.multiple(
            "src.graph.listing_workflow", **{k.rsplit(".", 1)[-1]: v for k, v in agents.items()}
        )
    )
    persistence = "src.graph.listing_workflow.listing_persistence"
    for fn in (
        "update_task_status",
        "save_push_results",
        "save_asset_packages",
        "save_copywriting_packages",
        "save_compliance_reports",
    ):
        stack.enter_context(patch(f"{persistence}.{fn}", new=AsyncMock()))
    return stack


class TestListingWorkflowRunPaths:
    """刊登工作流经公开 run 入口的终态与异常路径测试。"""

    @pytest.mark.asyncio
    async def test_run_without_product_ends_failed(self) -> None:
        """商品缺失时应快速失败并终态 failed。"""
        workflow = ListingWorkflow()
        with patch("src.graph.listing_workflow.listing_persistence.update_task_status"):
            result = await workflow.run(None, [Platform.AMAZON])
        assert result["current_step"] == "finalized"
        assert result["step_results"]["final_status"] == TaskStatus.FAILED.value
        assert any(e["node"] == "import_product" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_run_partial_success_gives_partial(self) -> None:
        """部分平台推送成功时终态应为 partial（刊登任务特有）。"""
        workflow = ListingWorkflow()
        service = _push_service(
            {
                "amazon": _push_result(True, Platform.AMAZON),
                "ebay": _push_result(False, Platform.EBAY),
            }
        )
        with _pipeline({"src.graph.listing_workflow.ListingPushService": service}):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON, Platform.EBAY], task_id=1, tenant_id="t1"
            )
        assert result["step_results"]["final_status"] == TaskStatus.PARTIAL.value

    @pytest.mark.asyncio
    async def test_run_all_success_gives_published(self) -> None:
        """全部平台推送成功时终态应为 published。"""
        workflow = ListingWorkflow()
        service = _push_service({"amazon": _push_result(True, Platform.AMAZON)})
        with _pipeline({"src.graph.listing_workflow.ListingPushService": service}):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON], task_id=1, tenant_id="t1"
            )
        assert result["step_results"]["final_status"] == TaskStatus.PUBLISHED.value

    @pytest.mark.asyncio
    async def test_run_compliance_blocked_suspends_reviewing(self) -> None:
        """合规 FAIL 平台应被阻断：不推送、终态挂起 reviewing。"""
        workflow = ListingWorkflow()
        report = ComplianceReport(
            listing_task_id=1, platform=Platform.AMAZON, overall=ComplianceStatus.FAIL
        )
        compliance = MagicMock()
        compliance.return_value.execute_sync = MagicMock(
            return_value={"compliance_reports": {Platform.AMAZON: report}}
        )
        service = _push_service({})
        with _pipeline(
            {
                "src.graph.listing_workflow.ComplianceCheckerAgent": compliance,
                "src.graph.listing_workflow.ListingPushService": service,
            }
        ):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON], task_id=1, tenant_id="t1"
            )
        assert result["step_results"]["final_status"] == TaskStatus.REVIEWING.value
        service.return_value.push_to_platforms.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_push_exception_ends_failed(self) -> None:
        """推送服务抛异常时应记录节点错误并终态 failed。"""
        workflow = ListingWorkflow()
        service = _push_service(error=RuntimeError("push exploded"))
        with _pipeline({"src.graph.listing_workflow.ListingPushService": service}):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON], task_id=1, tenant_id="t1"
            )
        assert result["step_results"]["final_status"] == TaskStatus.FAILED.value
        assert any(
            e["node"] == "platform_push" and "push exploded" in e["error"] for e in result["errors"]
        )

    @pytest.mark.asyncio
    async def test_run_optimizer_failure_records_error(self) -> None:
        """素材优化 Agent 抛异常时应记录节点错误，流程继续到终态。"""
        workflow = ListingWorkflow()
        optimizer = MagicMock()
        optimizer.return_value.execute_sync = MagicMock(side_effect=RuntimeError("opt boom"))
        service = _push_service({"amazon": _push_result(True, Platform.AMAZON)})
        with _pipeline(
            {
                "src.graph.listing_workflow.AssetOptimizerAgent": optimizer,
                "src.graph.listing_workflow.ListingPushService": service,
            }
        ):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON], task_id=1, tenant_id="t1"
            )
        assert any(
            e["node"] == "optimize_assets" and "opt boom" in e["error"] for e in result["errors"]
        )

    @pytest.mark.asyncio
    async def test_run_copywriter_failure_records_error(self) -> None:
        """文案 Agent 抛异常时应记录节点错误，流程继续到终态。"""
        workflow = ListingWorkflow()
        copywriter = MagicMock()
        copywriter.return_value.execute = AsyncMock(side_effect=RuntimeError("llm down"))
        service = _push_service({"amazon": _push_result(True, Platform.AMAZON)})
        with _pipeline(
            {
                "src.graph.listing_workflow.AICopywritingAgent": copywriter,
                "src.graph.listing_workflow.ListingPushService": service,
            }
        ):
            result = await workflow.run(
                _make_product(), [Platform.AMAZON], task_id=1, tenant_id="t1"
            )
        assert any(
            e["node"] == "generate_copy" and "llm down" in e["error"] for e in result["errors"]
        )

    @pytest.mark.asyncio
    async def test_run_import_load_failure_records_error(self) -> None:
        """AI 图片加载失败时应记录错误但不中断导入。"""
        workflow = ListingWorkflow()
        product = ListingProduct(
            sku="WF-SKU-2",
            title="With Source",
            attributes={"source_product_id": 99},
        )
        loader = MagicMock()
        loader.return_value.load_images = AsyncMock(side_effect=RuntimeError("db down"))
        service = _push_service({"amazon": _push_result(True, Platform.AMAZON)})
        session = AsyncMock()
        with patch("src.graph.listing_workflow.get_db_session") as mock_session_ctx:
            mock_session_ctx.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with _pipeline(
                {
                    "src.graph.listing_workflow.ListingAssetLoader": loader,
                    "src.graph.listing_workflow.ListingPushService": service,
                }
            ):
                result = await workflow.run(product, [Platform.AMAZON], task_id=1, tenant_id="t1")
        assert any(
            e["node"] == "import_product" and "db down" in e["error"] for e in result["errors"]
        )
        assert result["step_results"]["final_status"] == TaskStatus.PUBLISHED.value


class TestListingWorkflowResumePartial:
    """resume_push 部分成功终态判定测试（经公开推送服务替身）。"""

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

        service = _push_service(
            {
                "amazon": _push_result(True, Platform.AMAZON),
                "ebay": _push_result(False, Platform.EBAY),
            }
        )

        with patch("src.graph.listing_workflow.get_db_session") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            with (
                patch("src.graph.listing_workflow.ListingPushService", service),
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
                patch(
                    "src.graph.listing_workflow.listing_persistence.save_push_results",
                    new=AsyncMock(),
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
