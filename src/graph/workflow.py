"""
LangGraph工作流定义模块。

Description:
    构建多Agent协作的状态图工作流，定义节点和边的连接关系。
    支持 RAG 知识库增强的 Agent 注入。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

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
    ) -> None:
        """初始化工作流构建器。

        Args:
            retriever: 知识检索器实例（可选）。
            session: 数据库会话，用于 RAG 检索（可选）。
            rag_enabled: 是否启用 RAG 增强，默认启用。
        """
        self.graph = StateGraph(AgentState)
        self.checkpointer = MemorySaver()
        self._nodes_added = False
        self._edges_added = False
        self._retriever = retriever
        self._session = session
        self._rag_enabled = rag_enabled

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
            )
        from src.agents.requirement_analyzer import RequirementAnalyzerAgent

        return RequirementAnalyzerAgent()

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
            )
        from src.agents.creative_planner import CreativePlannerAgent

        return CreativePlannerAgent()

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
            )
        from src.agents.quality_reviewer import QualityReviewerAgent

        return QualityReviewerAgent()

    def add_agent_nodes(self) -> "WorkflowBuilder":
        """添加所有Agent节点。

        Returns:
            self，支持链式调用。
        """
        # 延迟导入以避免循环导入
        from src.agents.image_generator import ImageGeneratorAgent
        from src.agents.orchestrator import OrchestratorAgent
        from src.agents.video_generator import VideoGeneratorAgent
        from src.agents.visual_designer import VisualDesignerAgent

        # 创建 Agent 实例（根据 RAG 配置选择版本）
        orchestrator = OrchestratorAgent()
        requirement_analyzer = self._create_requirement_analyzer()
        creative_planner = self._create_creative_planner()
        visual_designer = VisualDesignerAgent()
        image_generator = ImageGeneratorAgent()
        video_generator = VideoGeneratorAgent()
        quality_reviewer = self._create_quality_reviewer()

        # 定义节点处理函数
        async def orchestrator_node(state: AgentState) -> dict:
            """编排器节点。"""
            # 记录开始日志
            start_log = create_agent_log("orchestrator", "running")

            result = await orchestrator.execute(state)

            # 记录结束日志
            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "orchestration",
                    "agent_logs": [start_log],
                }
            start_log.mark_completed("编排调度完成")
            return {
                "current_step": "orchestration",
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def requirement_analyzer_node(state: AgentState) -> dict:
            """需求分析节点。"""
            start_log = create_agent_log("requirement_analyzer", "running")

            result = await requirement_analyzer.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "requirement_analysis",
                    "agent_logs": [start_log],
                }
            start_log.mark_completed(
                f"分析完成，发现 {len(result.data.get('selling_points', []))} 个卖点"
            )
            return {
                "current_step": "requirement_analysis",
                "requirement_report": result.data.get("requirement_report"),
                "selling_points": result.data.get("selling_points", []),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def creative_planner_node(state: AgentState) -> dict:
            """创意策划节点。"""
            start_log = create_agent_log("creative_planner", "running")

            result = await creative_planner.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "creative_planning",
                    "agent_logs": [start_log],
                }
            start_log.mark_completed("创意方案生成完成")
            return {
                "current_step": "creative_planning",
                "creative_plan": result.data.get("creative_plan"),
                "color_palette": result.data.get("color_palette"),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def visual_designer_node(state: AgentState) -> dict:
            """视觉设计节点。"""
            start_log = create_agent_log("visual_designer", "running")

            result = await visual_designer.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "visual_design",
                    "agent_logs": [start_log],
                }
            prompts_count = len(result.data.get("image_prompts", []))
            start_log.mark_completed(f"生成 {prompts_count} 个图片提示词")
            return {
                "current_step": "visual_design",
                "generation_prompts": result.data.get("image_prompts", []),
                "storyboard": result.data.get("storyboard"),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def image_generator_node(state: AgentState) -> dict:
            """图片生成节点。"""
            start_log = create_agent_log("image_generator", "running")

            result = await image_generator.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "image_generation",
                    "agent_logs": [start_log],
                }
            images_count = len(result.data.get("generated_images", []))
            start_log.mark_completed(f"成功生成 {images_count} 张图片")
            return {
                "current_step": "image_generation",
                "generated_images": result.data.get("generated_images", []),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def video_generator_node(state: AgentState) -> dict:
            """视频生成节点。"""
            start_log = create_agent_log("video_generator", "running")

            result = await video_generator.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "video_generation",
                    "agent_logs": [start_log],
                }
            start_log.mark_completed("视频生成完成")
            return {
                "current_step": "video_generation",
                "generated_video": result.data.get("generated_video"),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        async def quality_reviewer_node(state: AgentState) -> dict:
            """质量审核节点。"""
            start_log = create_agent_log("quality_reviewer", "running")

            result = await quality_reviewer.execute(state)

            if not result.success:
                start_log.mark_failed(result.error or "执行失败")
                return {
                    "error": result.error,
                    "current_step": "quality_review",
                    "agent_logs": [start_log],
                }
            score = result.data.get("overall_score", 0)
            start_log.mark_completed(f"质量评分: {score}")
            return {
                "current_step": "quality_review",
                "quality_reports": result.data.get("quality_reports", []),
                "quality_score": result.data.get("overall_score"),
                "issues": result.data.get("issues", []),
                "asset_collection": result.data.get("asset_collection"),
                "final_results": result.data.get("final_results"),
                "completed_steps": state.completed_steps,
                "agent_logs": [start_log],
            }

        # 添加节点
        self.graph.add_node("orchestrator", orchestrator_node)
        self.graph.add_node("requirement_analyzer", requirement_analyzer_node)
        self.graph.add_node("creative_planner", creative_planner_node)
        self.graph.add_node("visual_designer", visual_designer_node)
        self.graph.add_node("image_generator", image_generator_node)
        self.graph.add_node("video_generator", video_generator_node)
        self.graph.add_node("quality_reviewer", quality_reviewer_node)

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

        # 条件路由函数
        def route_after_orchestrator(
            state: AgentState,
        ) -> Literal["requirement_analyzer", "end"]:
            """编排器后的路由。"""
            if state.has_error():
                return "end"
            return "requirement_analyzer"

        def route_after_design(
            state: AgentState,
        ) -> Literal["image_generator", "video_generator", "both", "end"]:
            """设计后的路由，根据任务类型决定生成方向。"""
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
                return "both"

        def route_after_generation(
            state: AgentState,
        ) -> Literal["quality_reviewer", "end"]:
            """生成后的路由。"""
            if state.has_error():
                return "end"
            return "quality_reviewer"

        # 添加条件边
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
                "both": "image_generator",  # 先走图片，再走视频
                "end": END,
            },
        )

        # 图片生成后到质量审核
        self.graph.add_conditional_edges(
            "image_generator",
            route_after_generation,
            {
                "quality_reviewer": "quality_reviewer",
                "end": END,
            },
        )

        # 视频生成后到质量审核
        self.graph.add_conditional_edges(
            "video_generator",
            route_after_generation,
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
) -> "CompiledGraph":
    """创建并编译完整的工作流。

    Args:
        retriever: 知识检索器实例（可选）。
        session: 数据库会话（可选）。
        rag_enabled: 是否启用 RAG 增强。

    Returns:
        编译后的工作流实例。
    """
    builder = WorkflowBuilder(
        retriever=retriever,
        session=session,
        rag_enabled=rag_enabled,
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
    ) -> None:
        """初始化工作流。

        Args:
            retriever: 知识检索器实例（可选）。
            session: 数据库会话（可选）。
            rag_enabled: 是否启用 RAG 增强。
        """
        self.app: CompiledGraph = create_workflow(
            retriever=retriever,
            session=session,
            rag_enabled=rag_enabled,
        )
        self._retriever = retriever
        self._session = session
        self._rag_enabled = rag_enabled

    async def run(
        self,
        product: Product,
        request: GenerationRequest | None = None,
        thread_id: str = "default",
    ) -> AgentState:
        """运行工作流。

        Args:
            product: 商品信息。
            request: 生成请求。
            thread_id: 会话线程ID。

        Returns:
            最终状态。
        """
        initial_state = create_initial_state(product, request)
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
        )
