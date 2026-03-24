"""
LangGraph工作流定义模块。

Description:
    构建多Agent协作的状态图工作流，定义节点和边的连接关系。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from src.graph.state import AgentState, create_initial_state


class WorkflowBuilder:
    """工作流构建器。

    负责构建和编译LangGraph状态图。

    Example:
        >>> builder = WorkflowBuilder()
        >>> builder.add_agent_nodes()
        >>> app = builder.compile()
        >>> result = await app.ainvoke(initial_state)
    """

    def __init__(self) -> None:
        """初始化工作流构建器。"""
        self.graph = StateGraph(AgentState)
        self.checkpointer = MemorySaver()
        self._nodes_added = False
        self._edges_added = False

    def add_agent_nodes(self) -> "WorkflowBuilder":
        """添加所有Agent节点。

        Returns:
            self，支持链式调用。
        """
        # 定义节点处理函数（占位符，实际Agent实现后替换）
        async def orchestrator_node(state: AgentState) -> dict:
            """编排器节点。"""
            state.set_current_step("orchestration")
            # TODO: 调用实际的OrchestratorAgent
            return {"current_step": "orchestration"}

        async def requirement_analyzer_node(state: AgentState) -> dict:
            """需求分析节点。"""
            state.set_current_step("requirement_analysis")
            # TODO: 调用实际的RequirementAnalyzerAgent
            return {"current_step": "requirement_analysis"}

        async def creative_planner_node(state: AgentState) -> dict:
            """创意策划节点。"""
            state.set_current_step("creative_planning")
            # TODO: 调用实际的CreativePlannerAgent
            return {"current_step": "creative_planning"}

        async def visual_designer_node(state: AgentState) -> dict:
            """视觉设计节点。"""
            state.set_current_step("visual_design")
            # TODO: 调用实际的VisualDesignerAgent
            return {"current_step": "visual_design"}

        async def image_generator_node(state: AgentState) -> dict:
            """图片生成节点。"""
            state.set_current_step("image_generation")
            # TODO: 调用实际的ImageGeneratorAgent
            return {"current_step": "image_generation"}

        async def video_generator_node(state: AgentState) -> dict:
            """视频生成节点。"""
            state.set_current_step("video_generation")
            # TODO: 调用实际的VideoGeneratorAgent
            return {"current_step": "video_generation"}

        async def quality_reviewer_node(state: AgentState) -> dict:
            """质量审核节点。"""
            state.set_current_step("quality_review")
            # TODO: 调用实际的QualityReviewerAgent
            return {"current_step": "quality_review"}

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
            raise RuntimeError(
                "请先调用 add_agent_nodes() 和 add_edges() 完成工作流构建"
            )

        return self.graph.compile(checkpointer=self.checkpointer)


def create_workflow() -> "CompiledGraph":
    """创建并编译完整的工作流。

    Returns:
        编译后的工作流实例。
    """
    builder = WorkflowBuilder()
    return (
        builder.add_agent_nodes()
        .add_edges()
        .compile()
    )


# 类型别名
CompiledGraph = StateGraph | None  # 实际类型由 compile() 返回


class ProductVisualWorkflow:
    """商品视觉生成工作流。

    封装完整的工作流执行逻辑。

    Example:
        >>> workflow = ProductVisualWorkflow()
        >>> result = await workflow.run(product, request)
    """

    def __init__(self) -> None:
        """初始化工作流。"""
        self.app = create_workflow()

    async def run(
        self,
        product,
        request=None,
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
        return state.values if state else None
