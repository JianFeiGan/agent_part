"""
LangGraph工作流定义模块。

Description:
    构建多Agent协作的状态图工作流，定义节点和边的连接关系。
    支持 RAG 知识库增强的 Agent 注入。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.graph.state import AgentLog, AgentState, GenerationRequest, create_initial_state
from src.models.product import Product

if TYPE_CHECKING:
    from langgraph.pregel import Pregel
    from sqlalchemy.ext.asyncio import AsyncSession


# Agent 名称映射
AGENT_NAMES = {
    "orchestrator": "编排调度Agent",
    "requirement_analyzer": "需求分析Agent",
    "creative_planner": "创意策划Agent",
    "visual_designer": "视觉设计Agent",
    "image_generator": "图片生成Agent",
    "video_generator": "视频生成Agent",
    "quality_reviewer": "质量审核Agent",
}


# ==================== 模块级路由函数 ====================


def route_after_orchestrator(
    state: AgentState,
) -> Literal["requirement_analyzer", "end"]:
    """编排器后的路由。

    Args:
        state: 当前 Agent 状态。

    Returns:
        下一个节点名称。
    """
    if state.has_error():
        return "end"
    return "requirement_analyzer"


def route_after_design(
    state: AgentState,
) -> Literal["image_generator", "video_generator", "end"]:
    """设计后的路由，根据任务类型决定生成方向。

    Args:
        state: 当前 Agent 状态。

    Returns:
        下一个节点名称。
    """
    if state.has_error():
        return "end"

    request = state.generation_request
    if request is None:
        return "end"

    task_type = request.task_type
    if task_type == "image_only":
        return "image_generator"
    elif task_type == "video_only":
        return "video_generator"
    else:
        return "image_generator"


def route_after_image_generation(
    state: AgentState,
) -> Literal["video_generator", "quality_reviewer", "end"]:
    """图片生成后的路由。

    image_only: 直接到质量审核。
    image_and_video: 必须到视频生成，不能跳过。

    Args:
        state: 当前 Agent 状态。

    Returns:
        下一个节点名称。
    """
    if state.has_error():
        return "end"

    request = state.generation_request
    if request is None:
        return "quality_reviewer"

    task_type = request.task_type
    if task_type == "image_and_video":
        return "video_generator"
    return "quality_reviewer"


def route_after_video_generation(
    state: AgentState,
) -> Literal["quality_reviewer", "end"]:
    """视频生成后的路由。

    Args:
        state: 当前 Agent 状态。

    Returns:
        下一个节点名称。
    """
    if state.has_error():
        return "end"
    return "quality_reviewer"


def create_agent_log(agent_key: str, status: str = "running") -> AgentLog:
    """创建 Agent 执行日志。

    Args:
        agent_key: Agent 标识。
        status: 日志状态。

    Returns:
        AgentLog 实例。
    """
    return AgentLog(
        agent_name=AGENT_NAMES.get(agent_key, agent_key),
        step=agent_key,
        start_time=datetime.now().isoformat() if status == "running" else None,
        status=status,
    )


def _apply_trace_to_log(agent: Any, log: AgentLog) -> None:
    """将 Agent 的 Trace 数据应用到日志。

    Args:
        agent: Agent 实例。
        log: AgentLog 实例。
    """
    trace = getattr(agent, "_last_trace", None)
    if not trace:
        return
    log.prompt_template = trace.get("prompt_template")
    log.prompt_variables = trace.get("prompt_variables")
    log.input_tokens = trace.get("input_tokens", 0)
    log.output_tokens = trace.get("output_tokens", 0)
    log.total_tokens = trace.get("total_tokens", 0)
    log.cost_cny = trace.get("cost_cny", 0.0)
    log.latency_ms = trace.get("latency_ms")
    log.model_name = trace.get("model_name")
    log.provider = trace.get("provider")



def make_agent_node(
    agent_key: str,
    step_name: str,
    agent: Any,
    result_mapper: Callable[[Any], dict[str, Any]],
    *,
    apply_trace: bool = True,
    summarize: str | Callable[[Any], str] = "",
    input_snapshot: Callable[[AgentState], dict[str, Any] | None] | None = None,
    output_snapshot: Callable[[Any], dict[str, Any] | None] | None = None,
) -> Any:
    """构建统一的 Agent 节点处理函数。

    封装所有节点共有的样板逻辑：执行日志创建、Agent 执行、Trace 回写、
    失败短路（写入 error）、成功时映射结果字段并累加 completed_steps。

    Args:
        agent_key: Agent 标识（用于日志）。
        step_name: 工作流步骤名（写入 current_step / completed_steps）。
        agent: Agent 实例。
        result_mapper: 从 AgentResult.data 提取要合并进状态的字段。
        apply_trace: 是否将 Agent 的 LLM Trace 回写到日志。
        summarize: 成功摘要文案，或接收 AgentResult 返回文案的回调。
        input_snapshot: 从当前状态生成输入快照（可选）。
        output_snapshot: 从执行结果生成输出快照（可选）。

    Returns:
        LangGraph 节点异步函数。
    """

    async def _node(state: AgentState) -> dict:
        """通用 Agent 节点。"""
        start_log = create_agent_log(agent_key, "running")

        result = await agent.execute(state)
        if apply_trace:
            _apply_trace_to_log(agent, start_log)

        if not result.success:
            start_log.mark_failed(result.error or "执行失败")
            if input_snapshot is not None:
                start_log.input_data = input_snapshot(state)
            return {
                "error": result.error,
                "current_step": step_name,
                "agent_logs": [start_log],
            }

        summary = summarize(result) if callable(summarize) else summarize
        start_log.mark_completed(summary)
        if input_snapshot is not None:
            start_log.input_data = input_snapshot(state)
        if output_snapshot is not None:
            start_log.output_data = output_snapshot(result)
        return {
            "current_step": step_name,
            **result_mapper(result),
            "completed_steps": [*state.completed_steps, step_name],
            "agent_logs": [start_log],
        }

    return _node


class WorkflowBuilder:
    """工作流构建器。

    负责构建和编译LangGraph状态图。
    支持 RAG 知识库增强的 Agent 注入。

    Example:
        >>> builder = WorkflowBuilder()
        >>> builder.add_agent_nodes()
        >>> app = builder.compile()
        >>> result = await app.ainvoke(initial_state)

        # 使用 RAG 增强模式
        >>> from src.rag.retriever import KnowledgeRetriever
        >>> retriever = KnowledgeRetriever()
        >>> builder = WorkflowBuilder(retriever=retriever, session=db_session)
    """

    def __init__(
        self,
        retriever: Any | None = None,
        session: "AsyncSession | None" = None,
        rag_enabled: bool = True,
        tenant_id: str = "system",
        task_id: str | None = None,
    ) -> None:
        """初始化工作流构建器。

        Args:
            retriever: 知识检索器实例（可选）。
            session: 数据库会话，用于 RAG 检索（可选）。
            rag_enabled: 是否启用 RAG 增强，默认启用。
            tenant_id: 租户 ID，注入各 Agent 用于隔离会话记录与资产归属。
            task_id: 关联任务 ID，用于 Agent 会话记录关联。
        """
        self.graph = StateGraph(AgentState)
        self.checkpointer = MemorySaver()
        self._nodes_added = False
        self._edges_added = False
        self._retriever = retriever
        self._session = session
        self._rag_enabled = rag_enabled
        self._tenant_id = tenant_id
        self._task_id = task_id

    def set_rag_dependencies(
        self,
        retriever: Any | None = None,
        session: "AsyncSession | None" = None,
    ) -> "WorkflowBuilder":
        """设置 RAG 依赖。

        Args:
            retriever: 知识检索器实例。
            session: 数据库会话。

        Returns:
            self，支持链式调用。
        """
        if retriever:
            self._retriever = retriever
        if session:
            self._session = session
        return self

    def _create_requirement_analyzer(self) -> Any:
        """创建需求分析 Agent。

        根据 RAG 配置选择普通或 RAG 增强版本。

        Returns:
            Agent 实例。
        """
        if self._rag_enabled and self._retriever:
            from src.agents.rag_requirement_analyzer import RAGEnhancedRequirementAnalyzer

            return RAGEnhancedRequirementAnalyzer(
                retriever=self._retriever,
                session=self._session,
                tenant_id=self._tenant_id,
                task_id=self._task_id,
            )
        from src.agents.requirement_analyzer import RequirementAnalyzerAgent

        return RequirementAnalyzerAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )

    def _create_creative_planner(self) -> Any:
        """创建创意策划 Agent。

        根据 RAG 配置选择普通或 RAG 增强版本。

        Returns:
            Agent 实例。
        """
        if self._rag_enabled and self._retriever:
            from src.agents.rag_creative_planner import RAGEnhancedCreativePlanner

            return RAGEnhancedCreativePlanner(
                retriever=self._retriever,
                session=self._session,
                tenant_id=self._tenant_id,
                task_id=self._task_id,
            )
        from src.agents.creative_planner import CreativePlannerAgent

        return CreativePlannerAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )

    def _create_quality_reviewer(self) -> Any:
        """创建质量审核 Agent。

        根据 RAG 配置选择普通或 RAG 增强版本。

        Returns:
            Agent 实例。
        """
        if self._rag_enabled and self._retriever:
            from src.agents.rag_quality_reviewer import RAGEnhancedQualityReviewer

            return RAGEnhancedQualityReviewer(
                retriever=self._retriever,
                session=self._session,
                tenant_id=self._tenant_id,
                task_id=self._task_id,
            )
        from src.agents.quality_reviewer import QualityReviewerAgent

        return QualityReviewerAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )

    def _create_image_generator(self) -> Any:
        """创建图片生成 Agent。

        根据 RAG 配置选择普通或 RAG 增强版本。

        Returns:
            Agent 实例。
        """
        if self._rag_enabled and self._retriever:
            from src.agents.rag_image_generator import RAGEnhancedImageGenerator

            return RAGEnhancedImageGenerator(
                retriever=self._retriever,
                session=self._session,
                tenant_id=self._tenant_id,
                task_id=self._task_id,
            )
        from src.agents.image_generator import ImageGeneratorAgent

        return ImageGeneratorAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )

    def add_agent_nodes(self) -> "WorkflowBuilder":
        """添加所有Agent节点。

        Returns:
            self，支持链式调用。
        """
        # 延迟导入以避免循环导入
        from src.agents.orchestrator import OrchestratorAgent
        from src.agents.video_generator import VideoGeneratorAgent
        from src.agents.visual_designer import VisualDesignerAgent

        # 创建 Agent 实例（根据 RAG 配置选择版本）
        orchestrator = OrchestratorAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )
        requirement_analyzer = self._create_requirement_analyzer()
        creative_planner = self._create_creative_planner()
        visual_designer = VisualDesignerAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )
        image_generator = self._create_image_generator()
        video_generator = VideoGeneratorAgent(
            tenant_id=self._tenant_id, task_id=self._task_id
        )
        quality_reviewer = self._create_quality_reviewer()

        # 使用统一工厂构建节点处理函数
        def _trunc(value: Any, limit: int = 500) -> str | None:
            return str(value)[:limit] if value else None

        node_defs = {
            "orchestrator": make_agent_node(
                "orchestrator",
                "orchestration",
                orchestrator,
                lambda _r: {},
                apply_trace=False,
                summarize="编排调度完成",
            ),
            "requirement_analyzer": make_agent_node(
                "requirement_analyzer",
                "requirement_analysis",
                requirement_analyzer,
                lambda r: {
                    "requirement_report": r.data.get("requirement_report"),
                    "selling_points": r.data.get("selling_points", []),
                },
                summarize=lambda r: (
                    f"分析完成，发现 {len(r.data.get('selling_points', []))} 个卖点"
                ),
                input_snapshot=lambda s: {"product_info": _trunc(s.product_info)},
                output_snapshot=lambda r: {
                    "selling_points_count": len(r.data.get("selling_points", [])),
                    "key_features_count": (
                        len(r.data.get("requirement_report", {}).get("key_features", []))
                        if r.data.get("requirement_report")
                        else 0
                    ),
                },
            ),
            "creative_planner": make_agent_node(
                "creative_planner",
                "creative_planning",
                creative_planner,
                lambda r: {
                    "creative_plan": r.data.get("creative_plan"),
                    "color_palette": r.data.get("color_palette"),
                },
                summarize="创意方案生成完成",
                input_snapshot=lambda s: (
                    {"selling_points_count": len(s.selling_points)}
                    if s.selling_points
                    else None
                ),
            ),
            "visual_designer": make_agent_node(
                "visual_designer",
                "visual_design",
                visual_designer,
                lambda r: {
                    "generation_prompts": r.data.get("image_prompts", []),
                    "storyboard": r.data.get("storyboard"),
                },
                summarize=lambda r: (
                    f"生成 {len(r.data.get('image_prompts', []))} 个图片提示词"
                ),
                input_snapshot=lambda s: {"creative_plan": _trunc(s.creative_plan)},
                output_snapshot=lambda r: {
                    "prompts_count": len(r.data.get("image_prompts", []))
                },
            ),
            "image_generator": make_agent_node(
                "image_generator",
                "image_generation",
                image_generator,
                lambda r: {"generated_images": r.data.get("generated_images", [])},
                apply_trace=False,
                summarize=lambda r: (
                    f"成功生成 {len(r.data.get('generated_images', []))} 张图片"
                ),
                input_snapshot=lambda s: (
                    {"prompts_count": len(s.generation_prompts)}
                    if s.generation_prompts
                    else None
                ),
                output_snapshot=lambda r: {
                    "images_count": len(r.data.get("generated_images", []))
                },
            ),
            "video_generator": make_agent_node(
                "video_generator",
                "video_generation",
                video_generator,
                lambda r: {"generated_video": r.data.get("generated_video")},
                apply_trace=False,
                summarize="视频生成完成",
            ),
            "quality_reviewer": make_agent_node(
                "quality_reviewer",
                "quality_review",
                quality_reviewer,
                lambda r: {
                    "quality_reports": r.data.get("quality_reports", []),
                    "quality_score": r.data.get("overall_score"),
                    "issues": r.data.get("issues", []),
                    "asset_collection": r.data.get("asset_collection"),
                    "final_results": r.data.get("final_results"),
                },
                summarize=lambda r: f"质量评分: {r.data.get('overall_score', 0)}",
                input_snapshot=lambda s: {
                    "images_count": len(s.generated_images),
                    "has_video": s.generated_video is not None,
                },
                output_snapshot=lambda r: {
                    "quality_score": r.data.get("overall_score"),
                    "issues_count": len(r.data.get("issues", [])),
                },
            ),
        }

        # 添加节点
        for node_name, node_fn in node_defs.items():
            self.graph.add_node(node_name, node_fn)

        self._nodes_added = True
        return self

    def add_edges(self) -> "WorkflowBuilder":
        """添加边和条件路由。

        Returns:
            self，支持链式调用。
        """
        if not self._nodes_added:
            raise RuntimeError("请先调用 add_agent_nodes() 添加节点")

        # 设置入口点
        self.graph.set_entry_point("orchestrator")

        # 添加条件边（使用模块级路由函数）
        self.graph.add_conditional_edges(
            "orchestrator",
            route_after_orchestrator,
            {
                "requirement_analyzer": "requirement_analyzer",
                "end": END,
            },
        )

        # 线性流程：需求分析 -> 创意策划 -> 视觉设计
        self.graph.add_edge("requirement_analyzer", "creative_planner")
        self.graph.add_edge("creative_planner", "visual_designer")

        # 视觉设计后的条件路由
        self.graph.add_conditional_edges(
            "visual_designer",
            route_after_design,
            {
                "image_generator": "image_generator",
                "video_generator": "video_generator",
                "end": END,
            },
        )

        # 图片生成后路由：image_and_video 到 video_generator，其他到 quality_reviewer
        self.graph.add_conditional_edges(
            "image_generator",
            route_after_image_generation,
            {
                "video_generator": "video_generator",
                "quality_reviewer": "quality_reviewer",
                "end": END,
            },
        )

        # 视频生成后到质量审核
        self.graph.add_conditional_edges(
            "video_generator",
            route_after_video_generation,
            {
                "quality_reviewer": "quality_reviewer",
                "end": END,
            },
        )

        # 质量审核后结束
        self.graph.add_edge("quality_reviewer", END)

        self._edges_added = True
        return self

    def compile(self) -> "CompiledGraph":
        """编译工作流。

        Returns:
            编译后的可执行图。
        """
        if not self._nodes_added or not self._edges_added:
            raise RuntimeError("请先调用 add_agent_nodes() 和 add_edges() 完成工作流构建")

        return self.graph.compile(checkpointer=self.checkpointer)


def create_workflow(
    retriever: Any | None = None,
    session: "AsyncSession | None" = None,
    rag_enabled: bool = True,
    tenant_id: str = "system",
    task_id: str | None = None,
) -> "CompiledGraph":
    """创建并编译完整的工作流。

    Args:
        retriever: 知识检索器实例（可选）。
        session: 数据库会话（可选）。
        rag_enabled: 是否启用 RAG 增强。
        tenant_id: 租户 ID，注入各 Agent。
        task_id: 关联任务 ID，注入各 Agent。

    Returns:
        编译后的工作流实例。
    """
    builder = WorkflowBuilder(
        retriever=retriever,
        session=session,
        rag_enabled=rag_enabled,
        tenant_id=tenant_id,
        task_id=task_id,
    )
    return builder.add_agent_nodes().add_edges().compile()


# 类型别名 - 编译后的图类型
if TYPE_CHECKING:
    CompiledGraph = Pregel
else:
    CompiledGraph = Any


class ProductVisualWorkflow:
    """商品视觉生成工作流。

    封装完整的工作流执行逻辑。
    支持 RAG 知识库增强模式。

    Example:
        >>> workflow = ProductVisualWorkflow()
        >>> result = await workflow.run(product, request)

        # 使用 RAG 增强模式
        >>> from src.rag.retriever import KnowledgeRetriever
        >>> retriever = KnowledgeRetriever()
        >>> workflow = ProductVisualWorkflow(retriever=retriever, session=db_session)
    """

    def __init__(
        self,
        retriever: Any | None = None,
        session: "AsyncSession | None" = None,
        rag_enabled: bool = True,
        tenant_id: str = "system",
        task_id: str | None = None,
    ) -> None:
        """初始化工作流。

        Args:
            retriever: 知识检索器实例（可选）。
            session: 数据库会话（可选）。
            rag_enabled: 是否启用 RAG 增强。
            tenant_id: 租户 ID，注入各 Agent 用于隔离会话记录与资产归属。
            task_id: 关联任务 ID，用于 Agent 会话记录关联。
        """
        self.app: CompiledGraph = create_workflow(
            retriever=retriever,
            session=session,
            rag_enabled=rag_enabled,
            tenant_id=tenant_id,
            task_id=task_id,
        )
        self._retriever = retriever
        self._session = session
        self._rag_enabled = rag_enabled
        self._tenant_id = tenant_id
        self._task_id = task_id

    async def run(
        self,
        product: Product,
        request: GenerationRequest | None = None,
        thread_id: str = "default",
        *,
        llm_provider_id: int | None = None,
        image_provider_id: int | None = None,
        video_provider_id: int | None = None,
    ) -> AgentState:
        """运行工作流。

        Args:
            product: 商品信息。
            request: 生成请求。
            thread_id: 会话线程ID。
            llm_provider_id: 任务级指定的 LLM 厂商 ID。
            image_provider_id: 任务级指定的图片厂商 ID。
            video_provider_id: 任务级指定的视频厂商 ID。

        Returns:
            最终状态。
        """
        initial_state = create_initial_state(
            product,
            request,
            llm_provider_id=llm_provider_id,
            image_provider_id=image_provider_id,
            video_provider_id=video_provider_id,
        )
        config = {"configurable": {"thread_id": thread_id}}

        result = await self.app.ainvoke(initial_state, config=config)
        # 将结果转换为 AgentState
        if isinstance(result, dict):
            return AgentState(**result)
        return result

    async def get_state(self, thread_id: str = "default") -> AgentState | None:
        """获取当前状态。

        Args:
            thread_id: 会话线程ID。

        Returns:
            当前状态。
        """
        config = {"configurable": {"thread_id": thread_id}}
        state = await self.app.aget_state(config)
        if state and state.values:
            if isinstance(state.values, dict):
                return AgentState(**state.values)
            return state.values
        return None

    def set_session(self, session: "AsyncSession") -> None:
        """设置数据库会话。

        注意：设置会话后需要重新创建工作流才能生效。

        Args:
            session: 数据库会话。
        """
        self._session = session
        self.app = create_workflow(
            retriever=self._retriever,
            session=self._session,
            rag_enabled=self._rag_enabled,
            tenant_id=self._tenant_id,
            task_id=self._task_id,
        )
