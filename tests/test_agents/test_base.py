"""
测试Agent模块。

Tests for Agent base class and implementations.
"""


from src.agents.base import AgentResult, AgentRole, AgentStatus
from src.graph.state import AgentState, GenerationRequest, create_initial_state
from src.models.product import Product, ProductCategory


class TestAgentRole:
    """测试Agent角色枚举。"""

    def test_role_values(self) -> None:
        """测试角色值。"""
        assert AgentRole.ORCHESTRATOR.value == "orchestrator"
        assert AgentRole.REQUIREMENT_ANALYZER.value == "requirement_analyzer"

    def test_all_roles_exist(self) -> None:
        """测试所有角色都存在。"""
        roles = list(AgentRole)
        assert len(roles) == 7


class TestAgentStatus:
    """测试Agent状态枚举。"""

    def test_status_values(self) -> None:
        """测试状态值。"""
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.COMPLETED.value == "completed"
        assert AgentStatus.FAILED.value == "failed"


class TestAgentResult:
    """测试Agent执行结果。"""

    def test_success_result(self) -> None:
        """测试成功结果。"""
        result = AgentResult(
            success=True,
            data={"key": "value"},
            next_agent=AgentRole.CREATIVE_PLANNER,
        )
        assert result.success is True
        assert result.data["key"] == "value"
        assert result.next_agent == AgentRole.CREATIVE_PLANNER

    def test_failure_result(self) -> None:
        """测试失败结果。"""
        result = AgentResult(
            success=False,
            error="测试错误",
        )
        assert result.success is False
        assert result.error == "测试错误"


class TestAgentState:
    """测试Agent状态。"""

    def test_create_state(self) -> None:
        """测试创建状态。"""
        state = AgentState()
        assert state.current_step == "init"
        assert state.completed_steps == []

    def test_mark_step_completed(self) -> None:
        """测试标记步骤完成。"""
        state = AgentState()
        state.mark_step_completed("step1")
        assert "step1" in state.completed_steps
        state.mark_step_completed("step1")  # 重复标记
        assert len(state.completed_steps) == 1

    def test_set_current_step(self) -> None:
        """测试设置当前步骤。"""
        state = AgentState()
        state.set_current_step("processing")
        assert state.current_step == "processing"

    def test_has_error(self) -> None:
        """测试错误检测。"""
        state = AgentState()
        assert state.has_error() is False
        state.error = "发生错误"
        assert state.has_error() is True

    def test_get_summary(self) -> None:
        """测试获取摘要。"""
        state = AgentState()
        summary = state.get_summary()
        assert "current_step" in summary
        assert "has_error" in summary


class TestCreateInitialState:
    """测试创建初始状态。"""

    def test_create_initial_state(self) -> None:
        """测试创建初始状态。"""
        product = Product(
            name="测试商品",
            category=ProductCategory.DIGITAL,
            description="这是一个测试商品的详细描述",
        )
        state = create_initial_state(product)
        assert state.product_info is not None
        assert state.product_info.name == "测试商品"
        assert state.current_step == "init"

    def test_create_initial_state_with_request(self) -> None:
        """测试带请求的初始状态。"""
        product = Product(
            name="测试商品",
            category=ProductCategory.DIGITAL,
            description="这是一个测试商品的详细描述",
        )
        request = GenerationRequest(
            task_id="task_001",
            task_type="image_only",
        )
        state = create_initial_state(product, request)
        assert state.generation_request is not None
        assert state.generation_request.task_type == "image_only"
