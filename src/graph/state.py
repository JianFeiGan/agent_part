"""
Agent状态定义模块。

Description:
    定义多Agent协作系统的状态结构，包括所有Agent之间传递的状态字段。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from datetime import datetime
from operator import add
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.assets import (
    AssetCollection,
    GeneratedImage,
    GeneratedVideo,
    QualityReport,
)
from src.models.creative import CreativePlan
from src.models.product import Product
from src.models.storyboard import Storyboard


class AgentLog(BaseModel):
    """Agent 执行日志。

    记录每个 Agent 的执行状态、时间和消息。

    Attributes:
        agent_name: Agent 名称。
        step: 步骤标识。
        start_time: 开始时间。
        end_time: 结束时间。
        status: 状态: pending/running/completed/failed。
        message: 执行消息/错误原因。
        output_summary: 输出摘要。

    Example:
        >>> log = AgentLog(
        ...     agent_name="需求分析Agent",
        ...     step="requirement_analysis",
        ...     start_time="2026-03-25T10:00:00",
        ...     status="running"
        ... )
    """

    agent_name: str = Field(..., description="Agent 名称")
    step: str = Field(..., description="步骤标识")
    start_time: str | None = Field(default=None, description="开始时间")
    end_time: str | None = Field(default=None, description="结束时间")
    status: str = Field(default="pending", description="状态: pending/running/completed/failed")
    message: str | None = Field(default=None, description="执行消息/错误原因")
    output_summary: str | None = Field(default=None, description="输出摘要")

    def mark_running(self) -> None:
        """标记为运行中。"""
        self.status = "running"
        self.start_time = datetime.now().isoformat()

    def mark_completed(self, output_summary: str | None = None) -> None:
        """标记为完成。

        Args:
            output_summary: 输出摘要。
        """
        self.status = "completed"
        self.end_time = datetime.now().isoformat()
        if output_summary:
            self.output_summary = output_summary

    def mark_failed(self, error_message: str) -> None:
        """标记为失败。

        Args:
            error_message: 错误信息。
        """
        self.status = "failed"
        self.end_time = datetime.now().isoformat()
        self.message = error_message


class TaskType(str):
    """任务类型。"""

    IMAGE_ONLY = "image_only"
    VIDEO_ONLY = "video_only"
    IMAGE_AND_VIDEO = "image_and_video"


class GenerationRequest(BaseModel):
    """生成请求。"""

    task_id: str = Field(default_factory=lambda: "task_default", description="任务ID")
    task_type: str = Field(default="image_and_video", description="任务类型")

    # 图片生成配置
    image_types: list[str] = Field(
        default_factory=lambda: ["main", "scene", "selling_point"],
        description="图片类型列表",
    )
    image_count_per_type: int = Field(default=1, description="每种类型的图片数量")

    # 视频生成配置
    video_duration: float = Field(default=30.0, description="视频时长(秒)")
    video_style: str = Field(default="professional", description="视频风格")

    # 风格配置
    style_preference: str | None = Field(default=None, description="风格偏好")
    color_preference: str | None = Field(default=None, description="颜色偏好")

    # 质量配置
    quality_level: str = Field(default="standard", description="质量等级")


class RequirementReport(BaseModel):
    """需求分析报告。"""

    product_summary: str = Field(..., description="商品摘要")
    key_features: list[str] = Field(default_factory=list, description="关键特性")
    selling_points: list[dict[str, Any]] = Field(default_factory=list, description="卖点列表")
    target_audience: list[str] = Field(default_factory=list, description="目标人群")
    style_recommendations: list[str] = Field(default_factory=list, description="风格推荐")
    keywords: list[str] = Field(default_factory=list, description="关键词")


class AgentState(BaseModel):
    """多Agent协作系统状态。

    定义了在整个Agent协作流程中传递的状态结构。
    使用 Annotated 实现字段的累加操作。

    Attributes:
        product_info: 商品信息。
        generation_request: 生成请求配置。
        requirement_report: 需求分析报告。
        creative_plan: 创意方案。
        storyboard: 分镜脚本。
        generated_images: 生成的图片列表。
        generated_video: 生成的视频。
        quality_reports: 质量报告列表。
        asset_collection: 资源集合。
        final_results: 最终结果。
        error: 错误信息。

    Example:
        >>> state = AgentState(
        ...     product_info={"name": "智能手表"},
        ...     generation_request=GenerationRequest()
        ... )
    """

    # ==================== 输入 ====================
    product_info: Product | None = Field(default=None, description="商品信息")
    generation_request: GenerationRequest | None = Field(default=None, description="生成请求")

    # ==================== 分析阶段 ====================
    requirement_report: RequirementReport | None = Field(default=None, description="需求分析报告")
    selling_points: Annotated[list[dict[str, Any]], add] = Field(
        default_factory=list, description="提取的卖点列表（累加）"
    )

    # ==================== 创意阶段 ====================
    creative_plan: CreativePlan | None = Field(default=None, description="创意方案")
    color_palette: dict[str, Any] | None = Field(default=None, description="配色方案")

    # ==================== 设计阶段 ====================
    generation_prompts: Annotated[list[dict[str, Any]], add] = Field(
        default_factory=list, description="生成提示词列表（累加）"
    )

    # ==================== 生成阶段 ====================
    generated_images: Annotated[list[GeneratedImage], add] = Field(
        default_factory=list, description="生成的图片列表（累加）"
    )
    storyboard: Storyboard | None = Field(default=None, description="分镜脚本")
    generated_video: GeneratedVideo | None = Field(default=None, description="生成的视频")

    # ==================== 审核阶段 ====================
    quality_reports: Annotated[list[QualityReport], add] = Field(
        default_factory=list, description="质量报告列表（累加）"
    )
    quality_score: float | None = Field(default=None, description="总体质量评分")
    issues: Annotated[list[dict[str, Any]], add] = Field(
        default_factory=list, description="问题列表（累加）"
    )

    # ==================== 输出 ====================
    asset_collection: AssetCollection | None = Field(default=None, description="资源集合")
    final_results: dict[str, Any] | None = Field(default=None, description="最终结果")
    error: str | None = Field(default=None, description="错误信息")

    # ==================== 元数据 ====================
    current_step: str = Field(default="init", description="当前步骤")
    completed_steps: list[str] = Field(default_factory=list, description="已完成步骤")

    # ==================== Agent 执行日志 ====================
    agent_logs: Annotated[list[AgentLog], add] = Field(
        default_factory=list, description="Agent 执行日志列表（累加）"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def mark_step_completed(self, step: str) -> None:
        """标记步骤完成。

        Args:
            step: 步骤名称。
        """
        if step not in self.completed_steps:
            self.completed_steps.append(step)

    def set_current_step(self, step: str) -> None:
        """设置当前步骤。

        Args:
            step: 步骤名称。
        """
        self.current_step = step

    def has_error(self) -> bool:
        """检查是否有错误。

        Returns:
            是否有错误。
        """
        return self.error is not None

    def get_summary(self) -> dict[str, Any]:
        """获取状态摘要。

        Returns:
            状态摘要字典。
        """
        return {
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "has_product": self.product_info is not None,
            "has_creative_plan": self.creative_plan is not None,
            "images_count": len(self.generated_images),
            "has_video": self.generated_video is not None,
            "quality_score": self.quality_score,
            "has_error": self.has_error(),
            "agent_logs_count": len(self.agent_logs),
        }


def create_initial_state(
    product: Product,
    request: GenerationRequest | None = None,
) -> AgentState:
    """创建初始状态。

    Args:
        product: 商品信息。
        request: 生成请求，可选。

    Returns:
        初始化的Agent状态。
    """
    return AgentState(
        product_info=product,
        generation_request=request or GenerationRequest(),
        current_step="init",
    )
