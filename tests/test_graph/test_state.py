"""
测试状态图模块。

Tests for workflow state and graph.
"""

import pytest

from src.graph.state import AgentState, GenerationRequest, RequirementReport
from src.graph.workflow import WorkflowBuilder


class TestGenerationRequest:
    """测试生成请求。"""

    def test_create_request(self) -> None:
        """测试创建请求。"""
        request = GenerationRequest(
            task_id="task_001",
            task_type="image_and_video",
        )
        assert request.task_id == "task_001"
        assert request.task_type == "image_and_video"

    def test_request_defaults(self) -> None:
        """测试请求默认值。"""
        request = GenerationRequest(task_id="task_002")
        assert request.image_types == ["main", "scene", "selling_point"]
        assert request.video_duration == 30.0
        assert request.quality_level == "standard"


class TestRequirementReport:
    """测试需求分析报告。"""

    def test_create_report(self) -> None:
        """测试创建报告。"""
        report = RequirementReport(
            product_summary="智能运动手表",
            key_features=["健康监测", "运动追踪"],
            selling_points=[
                {"title": "长续航", "priority": 5},
            ],
            target_audience=["运动爱好者"],
            style_recommendations=["科技风"],
            keywords=["智能", "手表"],
        )
        assert report.product_summary == "智能运动手表"
        assert len(report.key_features) == 2


class TestWorkflowBuilder:
    """测试工作流构建器。"""

    def test_create_builder(self) -> None:
        """测试创建构建器。"""
        builder = WorkflowBuilder()
        assert builder is not None
        assert builder._nodes_added is False
        assert builder._edges_added is False

    def test_add_nodes(self) -> None:
        """测试添加节点。"""
        builder = WorkflowBuilder()
        builder.add_agent_nodes()
        assert builder._nodes_added is True

    def test_compile_workflow(self) -> None:
        """测试编译工作流。"""
        builder = WorkflowBuilder()
        builder.add_agent_nodes()
        builder.add_edges()
        app = builder.compile()
        assert app is not None

    def test_compile_without_nodes_raises(self) -> None:
        """测试未添加节点时编译会报错。"""
        builder = WorkflowBuilder()
        with pytest.raises(RuntimeError):
            builder.compile()


class TestStateAccumulation:
    """测试状态字段的累加操作。"""

    def test_selling_points_accumulation(self) -> None:
        """测试卖点累加。"""
        state = AgentState()
        # 模拟累加操作
        state.selling_points.append({"title": "卖点1"})
        state.selling_points.append({"title": "卖点2"})
        assert len(state.selling_points) == 2

    def test_generated_images_accumulation(self) -> None:
        """测试图片累加。"""
        from src.models.assets import AssetStatus, GeneratedImage

        state = AgentState()
        img1 = GeneratedImage(
            image_id="img_001",
            image_type="main",
            prompt="test",
            status=AssetStatus.PENDING,
        )
        img2 = GeneratedImage(
            image_id="img_002",
            image_type="scene",
            prompt="test",
            status=AssetStatus.PENDING,
        )
        state.generated_images.append(img1)
        state.generated_images.append(img2)
        assert len(state.generated_images) == 2
