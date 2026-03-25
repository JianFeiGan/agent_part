"""
资源 DTO 模型。

Description:
    定义资源相关的 API 响应模型，包括图片、视频、质量报告等。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.assets import AssetStatus, ImageFormat, VideoFormat


class ImageResponse(BaseModel):
    """图片响应模型。

    用于图片信息的 API 响应。

    Attributes:
        image_id: 图片ID。
        image_type: 图片类型。
        prompt: 生成提示词。
        url: 图片URL。
        format: 图片格式。
        width: 宽度(像素)。
        height: 高度(像素)。
        file_size: 文件大小(字节)。
        status: 状态。
        error_message: 错误信息。
        created_at: 创建时间。
        completed_at: 完成时间。
    """

    image_id: str = Field(..., description="图片ID")
    image_type: str = Field(..., description="图片类型")

    # 生成信息
    prompt: str = Field(..., description="生成提示词")

    # 资源信息
    url: str | None = Field(default=None, description="图片URL")
    format: ImageFormat = Field(default=ImageFormat.PNG, description="图片格式")

    # 规格信息
    width: int = Field(default=1024, description="宽度(像素)")
    height: int = Field(default=1024, description="高度(像素)")
    file_size: int | None = Field(default=None, description="文件大小(字节)")

    # 状态信息
    status: AssetStatus = Field(default=AssetStatus.PENDING, description="状态")
    error_message: str | None = Field(default=None, description="错误信息")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image_id": "img_001",
                    "image_type": "main",
                    "prompt": "Product photography of smart watch",
                    "url": "https://example.com/images/img_001.png",
                    "format": "png",
                    "width": 1024,
                    "height": 1024,
                    "status": "completed",
                    "created_at": "2026-03-25T10:00:00",
                    "completed_at": "2026-03-25T10:01:00",
                }
            ]
        }
    }


class VideoResponse(BaseModel):
    """视频响应模型。

    用于视频信息的 API 响应。

    Attributes:
        video_id: 视频ID。
        title: 视频标题。
        url: 视频URL。
        format: 视频格式。
        width: 宽度(像素)。
        height: 高度(像素)。
        duration: 时长(秒)。
        fps: 帧率。
        file_size: 文件大小(字节)。
        progress: 生成进度(0-100)。
        status: 状态。
        error_message: 错误信息。
        created_at: 创建时间。
        completed_at: 完成时间。
    """

    video_id: str = Field(..., description="视频ID")
    title: str | None = Field(default=None, description="视频标题")

    # 资源信息
    url: str | None = Field(default=None, description="视频URL")
    format: VideoFormat = Field(default=VideoFormat.MP4, description="视频格式")

    # 规格信息
    width: int = Field(default=1920, description="宽度(像素)")
    height: int = Field(default=1080, description="高度(像素)")
    duration: float = Field(..., description="时长(秒)")
    fps: int = Field(default=30, description="帧率")
    file_size: int | None = Field(default=None, description="文件大小(字节)")

    # 状态信息
    progress: float = Field(default=0.0, ge=0, le=100, description="生成进度(%)")
    status: AssetStatus = Field(default=AssetStatus.PENDING, description="状态")
    error_message: str | None = Field(default=None, description="错误信息")

    # 时间戳
    created_at: datetime = Field(..., description="创建时间")
    completed_at: datetime | None = Field(default=None, description="完成时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "video_id": "vid_001",
                    "title": "智能手表产品视频",
                    "url": "https://example.com/videos/vid_001.mp4",
                    "format": "mp4",
                    "width": 1920,
                    "height": 1080,
                    "duration": 30.0,
                    "fps": 30,
                    "progress": 100.0,
                    "status": "completed",
                    "created_at": "2026-03-25T10:00:00",
                    "completed_at": "2026-03-25T10:30:00",
                }
            ]
        }
    }


class QualityScoreResponse(BaseModel):
    """质量评分响应模型。

    Attributes:
        overall_score: 总体评分(0-1)。
        clarity_score: 清晰度评分(0-1)。
        composition_score: 构图评分(0-1)。
        color_score: 色彩评分(0-1)。
        relevance_score: 相关性评分(0-1)。
    """

    overall_score: float = Field(..., ge=0, le=1, description="总体评分")
    clarity_score: float = Field(default=0.8, ge=0, le=1, description="清晰度评分")
    composition_score: float = Field(default=0.8, ge=0, le=1, description="构图评分")
    color_score: float = Field(default=0.8, ge=0, le=1, description="色彩评分")
    relevance_score: float = Field(default=0.8, ge=0, le=1, description="相关性评分")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "overall_score": 0.92,
                    "clarity_score": 0.95,
                    "composition_score": 0.90,
                    "color_score": 0.88,
                    "relevance_score": 0.95,
                }
            ]
        }
    }


class QualityIssueResponse(BaseModel):
    """质量问题响应模型。

    Attributes:
        issue_type: 问题类型。
        severity: 严重程度。
        description: 问题描述。
        suggestion: 改进建议。
    """

    issue_type: str = Field(..., description="问题类型")
    severity: str = Field(..., description="严重程度: low/medium/high")
    description: str = Field(..., description="问题描述")
    suggestion: str | None = Field(default=None, description="改进建议")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "issue_type": "blur",
                    "severity": "medium",
                    "description": "图片边缘存在轻微模糊",
                    "suggestion": "尝试提高生成质量参数",
                }
            ]
        }
    }


class QualityReportResponse(BaseModel):
    """质量报告响应模型。

    用于质量审核结果的 API 响应。

    Attributes:
        asset_id: 资源ID。
        asset_type: 资源类型。
        score: 质量评分。
        issues: 问题列表。
        passed: 是否通过。
        review_comments: 审核意见。
        reviewed_at: 审核时间。
    """

    asset_id: str = Field(..., description="资源ID")
    asset_type: str = Field(..., description="资源类型: image/video")

    # 评分
    score: QualityScoreResponse = Field(..., description="质量评分")

    # 问题列表
    issues: list[QualityIssueResponse] = Field(
        default_factory=list, description="问题列表"
    )

    # 审核结果
    passed: bool = Field(..., description="是否通过")
    review_comments: str | None = Field(default=None, description="审核意见")

    # 时间戳
    reviewed_at: datetime = Field(..., description="审核时间")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "asset_id": "img_001",
                    "asset_type": "image",
                    "score": {
                        "overall_score": 0.92,
                        "clarity_score": 0.95,
                        "composition_score": 0.90,
                        "color_score": 0.88,
                        "relevance_score": 0.95,
                    },
                    "issues": [],
                    "passed": True,
                    "review_comments": "图片质量优秀，符合发布标准。",
                    "reviewed_at": "2026-03-25T10:05:00",
                }
            ]
        }
    }