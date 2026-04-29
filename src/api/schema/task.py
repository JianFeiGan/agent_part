"""
任务 DTO 模型。

Description:
    定义任务相关的 API 请求和响应模型。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from src.api.schema.asset import ImageResponse, QualityReportResponse, VideoResponse


class TaskType(str, Enum):
    """任务类型枚举。"""

    IMAGE_ONLY = "image_only"
    VIDEO_ONLY = "video_only"
    IMAGE_AND_VIDEO = "image_and_video"


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskCreateRequest(BaseModel):
    """创建任务请求模型。

    用于创建生成任务的 API 请求体。

    Attributes:
        product_id: 商品ID。
        task_type: 任务类型。
        image_types: 图片类型列表。
        image_count_per_type: 每种类型的图片数量。
        video_duration: 视频时长(秒)。
        video_style: 视频风格。
        style_preference: 风格偏好。
        color_preference: 颜色偏好。
        quality_level: 质量等级。
    """

    product_id: str = Field(..., description="商品ID")
    task_type: TaskType = Field(default=TaskType.IMAGE_AND_VIDEO, description="任务类型")

    # 图片生成配置
    image_types: list[str] = Field(
        default_factory=lambda: ["main", "scene", "selling_point"],
        description="图片类型列表",
    )
    image_count_per_type: int = Field(default=1, ge=1, le=10, description="每种类型的图片数量")

    # 视频生成配置
    video_duration: float = Field(default=30.0, ge=5.0, le=300.0, description="视频时长(秒)")
    video_style: str = Field(default="professional", description="视频风格")

    # 风格配置
    style_preference: str | None = Field(default=None, description="风格偏好")
    color_preference: str | None = Field(default=None, description="颜色偏好")

    # 质量配置
    quality_level: str = Field(default="standard", description="质量等级")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_id": "prod_001",
                    "task_type": "image_and_video",
                    "image_types": ["main", "scene", "selling_point"],
                    "image_count_per_type": 2,
                    "video_duration": 30.0,
                    "video_style": "professional",
                    "style_preference": "简约现代",
                    "color_preference": "蓝色系",
                    "quality_level": "standard",
                }
            ]
        }
    }


class TaskStatusResponse(BaseModel):
    """任务状态响应模型。

    用于查询任务状态的 API 响应。

    Attributes:
        task_id: 任务ID。
        status: 任务状态。
        progress: 完成进度（0-100）。
        current_step: 当前步骤。
        completed_steps: 已完成步骤列表。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: float = Field(default=0.0, ge=0, le=100, description="完成进度(%)")
    current_step: str = Field(..., description="当前步骤")
    completed_steps: list[str] = Field(default_factory=list, description="已完成步骤列表")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "task_001",
                    "status": "running",
                    "progress": 45.5,
                    "current_step": "image_generation",
                    "completed_steps": ["requirement_analysis", "creative_planning"],
                    "created_at": "2026-03-25T10:00:00",
                    "updated_at": "2026-03-25T10:15:00",
                }
            ]
        }
    }


class TaskDetailResponse(BaseModel):
    """任务详情响应模型。

    用于查询任务详情的 API 响应，包含完整的任务信息。

    Attributes:
        task_id: 任务ID。
        product_id: 商品ID。
        task_type: 任务类型。
        status: 任务状态。
        progress: 完成进度（0-100）。
        current_step: 当前步骤。
        completed_steps: 已完成步骤列表。
        agent_logs: Agent执行日志。
        images: 生成的图片列表。
        video: 生成的视频。
        quality_reports: 质量报告列表。
        error_message: 错误信息。
        created_at: 创建时间。
        updated_at: 更新时间。
    """

    task_id: str = Field(..., description="任务ID")
    product_id: str = Field(..., description="商品ID")
    task_type: TaskType = Field(..., description="任务类型")
    status: TaskStatus = Field(..., description="任务状态")
    progress: float = Field(default=0.0, ge=0, le=100, description="完成进度(%)")
    current_step: str = Field(..., description="当前步骤")
    completed_steps: list[str] = Field(default_factory=list, description="已完成步骤列表")
    agent_logs: list[dict] = Field(default_factory=list, description="Agent执行日志")

    # 生成结果
    images: list[ImageResponse] = Field(default_factory=list, description="生成的图片列表")
    video: VideoResponse | None = Field(default=None, description="生成的视频")
    quality_reports: list[QualityReportResponse] = Field(
        default_factory=list, description="质量报告列表"
    )

    # 错误信息
    error_message: str | None = Field(default=None, description="错误信息")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "task_id": "task_001",
                    "product_id": "prod_001",
                    "task_type": "image_and_video",
                    "status": "completed",
                    "progress": 100.0,
                    "current_step": "completed",
                    "completed_steps": [
                        "requirement_analysis",
                        "creative_planning",
                        "image_generation",
                        "video_generation",
                        "quality_review",
                    ],
                    "images": [
                        {
                            "image_id": "img_001",
                            "image_type": "main",
                            "url": "https://example.com/images/img_001.png",
                            "status": "completed",
                        }
                    ],
                    "video": {
                        "video_id": "vid_001",
                        "url": "https://example.com/videos/vid_001.mp4",
                        "duration": 30.0,
                        "status": "completed",
                    },
                    "quality_reports": [],
                    "created_at": "2026-03-25T10:00:00",
                    "updated_at": "2026-03-25T10:30:00",
                }
            ]
        }
    }


class TaskListQuery(BaseModel):
    """任务列表查询参数模型。

    用于任务列表查询接口的请求参数。

    Attributes:
        product_id: 商品ID。
        task_type: 任务类型。
        status: 任务状态。
        page: 页码。
        page_size: 每页大小。
    """

    product_id: str | None = Field(default=None, description="商品ID")
    task_type: TaskType | None = Field(default=None, description="任务类型")
    status: TaskStatus | None = Field(default=None, description="任务状态")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页大小")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"status": "running", "page": 1, "page_size": 10},
                {"product_id": "prod_001", "task_type": "image_and_video"},
            ]
        }
    }
