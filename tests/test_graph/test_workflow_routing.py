"""
测试工作流路由逻辑。

覆盖 image_only / video_only / image_and_video / error 分支。
验证:
  - image_only: orchestrator -> ... -> image_generator -> quality_reviewer
  - video_only: orchestrator -> ... -> video_generator -> quality_reviewer
  - image_and_video: orchestrator -> ... -> image_generator -> video_generator -> quality_reviewer
  - error 分支: 各路由在 has_error() 时返回 "end"
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.graph.state import AgentState, GenerationRequest
from src.graph.workflow import (
    WorkflowBuilder,
    route_after_orchestrator,
    route_after_design,
    route_after_image_generation,
    route_after_video_generation,
)
from src.models.product import Product, ProductCategory


@pytest.fixture
def sample_product() -> Product:
    """创建示例商品。"""
    return Product(
        product_id="test_routing_001",
        name="智能手表 Pro",
        brand="TechBrand",
        category=ProductCategory.DIGITAL,
        description="高端智能手表。",
        selling_points=[],
        specifications=[],
    )


def _make_state(
    task_type: str = "image_and_video",
    error: str | None = None,
) -> AgentState:
    """创建测试用的 AgentState。"""
    return AgentState(
        product_info=Product(
            product_id="test_001",
            name="Test Product",
            brand="TestBrand",
            category=ProductCategory.DIGITAL,
            description="Test description",
        ),
        generation_request=GenerationRequest(
            task_id="task_001",
            task_type=task_type,
        ),
        error=error,
    )


class TestRouteAfterOrchestrator:
    """route_after_orchestrator 路由函数测试。"""

    def test_normal_flow(self) -> None:
        """无错误时返回 requirement_analyzer。"""
        state = _make_state()
        result = route_after_orchestrator(state)
        assert result == "requirement_analyzer"

    def test_error_flow(self) -> None:
        """有错误时返回 end。"""
        state = _make_state(error="编排失败")
        result = route_after_orchestrator(state)
        assert result == "end"


class TestRouteAfterDesign:
    """route_after_design 路由函数测试。"""

    def test_image_only(self) -> None:
        """image_only 返回 image_generator。"""
        state = _make_state(task_type="image_only")
        result = route_after_design(state)
        assert result == "image_generator"

    def test_video_only(self) -> None:
        """video_only 返回 video_generator。"""
        state = _make_state(task_type="video_only")
        result = route_after_design(state)
        assert result == "video_generator"

    def test_image_and_video(self) -> None:
        """image_and_video 返回 image_generator。"""
        state = _make_state(task_type="image_and_video")
        result = route_after_design(state)
        assert result == "image_generator"

    def test_error_flow(self) -> None:
        """有错误时返回 end。"""
        state = _make_state(task_type="image_only", error="设计失败")
        result = route_after_design(state)
        assert result == "end"

    def test_none_request_returns_end(self) -> None:
        """无 generation_request 时返回 end。"""
        state = AgentState(
            product_info=Product(
                product_id="test_001",
                name="Test Product",
                brand="TestBrand",
                category=ProductCategory.DIGITAL,
                description="Test description",
            ),
            generation_request=None,
        )
        result = route_after_design(state)
        assert result == "end"


class TestRouteAfterImageGeneration:
    """route_after_image_generation 路由函数测试。"""

    def test_image_only_goes_to_quality_reviewer(self) -> None:
        """image_only: 图片生成后直接到质量审核。"""
        state = _make_state(task_type="image_only")
        result = route_after_image_generation(state)
        assert result == "quality_reviewer"

    def test_image_and_video_goes_to_video_generator(self) -> None:
        """image_and_video: 图片生成后到视频生成，不能跳过视频。"""
        state = _make_state(task_type="image_and_video")
        result = route_after_image_generation(state)
        assert result == "video_generator"

    def test_error_flow(self) -> None:
        """有错误时返回 end。"""
        state = _make_state(task_type="image_only", error="图片生成失败")
        result = route_after_image_generation(state)
        assert result == "end"


class TestRouteAfterVideoGeneration:
    """route_after_video_generation 路由函数测试。"""

    def test_normal_flow(self) -> None:
        """无错误时返回 quality_reviewer。"""
        state = _make_state(task_type="image_and_video")
        result = route_after_video_generation(state)
        assert result == "quality_reviewer"

    def test_video_only_goes_to_quality_reviewer(self) -> None:
        """video_only: 视频生成后到质量审核。"""
        state = _make_state(task_type="video_only")
        result = route_after_video_generation(state)
        assert result == "quality_reviewer"

    def test_error_flow(self) -> None:
        """有错误时返回 end。"""
        state = _make_state(task_type="video_only", error="视频生成失败")
        result = route_after_video_generation(state)
        assert result == "end"


class TestWorkflowBuilderEdges:
    """WorkflowBuilder.add_edges() 集成测试。"""

    def test_add_edges_sets_flag(self) -> None:
        """add_edges 设置 _edges_added 标志。"""
        builder = WorkflowBuilder()
        builder.add_agent_nodes()
        builder.add_edges()
        assert builder._edges_added is True

    def test_add_edges_without_nodes_raises(self) -> None:
        """未添加节点时调用 add_edges 报错。"""
        builder = WorkflowBuilder()
        with pytest.raises(RuntimeError, match="请先调用 add_agent_nodes"):
            builder.add_edges()

    def test_compiled_graph_has_all_nodes(self) -> None:
        """编译后的图包含所有节点。"""
        builder = WorkflowBuilder()
        builder.add_agent_nodes()
        builder.add_edges()
        app = builder.compile()

        # 验证编译成功且包含所有节点
        assert app is not None
        # 通过 nodes 属性检查节点存在
        node_names = list(app.get_graph().nodes.keys())
        expected_nodes = [
            "__start__",
            "orchestrator",
            "requirement_analyzer",
            "creative_planner",
            "visual_designer",
            "image_generator",
            "video_generator",
            "quality_reviewer",
        ]
        for node in expected_nodes:
            assert node in node_names, f"Node '{node}' not found in graph"


class TestImageAndVideoWorkflowRouting:
    """image_and_video 任务类型的完整路由验证。

    确保 image_generator -> video_generator -> quality_reviewer 顺序。
    """

    def test_image_and_video_routing_chain(self) -> None:
        """验证 image_and_video 的路由链路。"""
        state = _make_state(task_type="image_and_video")

        # Step 1: orchestrator 后 -> requirement_analyzer
        assert route_after_orchestrator(state) == "requirement_analyzer"

        # Step 2: visual_designer 后 -> image_generator
        assert route_after_design(state) == "image_generator"

        # Step 3: image_generator 后 -> video_generator（关键：不能到 quality_reviewer）
        assert route_after_image_generation(state) == "video_generator"

        # Step 4: video_generator 后 -> quality_reviewer
        assert route_after_video_generation(state) == "quality_reviewer"
