"""
生成资源模型。

Description:
    定义生成内容相关的数据结构，包括图片、视频、资源集合等。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AssetStatus(str, Enum):
    """资源状态枚举。"""

    PENDING = "pending"  # 待生成
    GENERATING = "generating"  # 生成中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 生成失败
    REVIEWING = "reviewing"  # 审核中
    APPROVED = "approved"  # 审核通过
    REJECTED = "rejected"  # 审核拒绝


class ImageFormat(str, Enum):
    """图片格式枚举。"""

    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class VideoFormat(str, Enum):
    """视频格式枚举。"""

    MP4 = "mp4"
    WEBM = "webm"
    MOV = "mov"


class GeneratedImage(BaseModel):
    """生成的图片资源。"""

    # 基本信息
    image_id: str = Field(..., description="图片ID")
    image_type: str = Field(..., description="图片类型")

    # 生成信息
    prompt: str = Field(..., description="生成提示词")
    negative_prompt: str | None = Field(default=None, description="负向提示词")

    # 资源信息
    url: str | None = Field(default=None, description="图片URL")
    local_path: str | None = Field(default=None, description="本地存储路径")
    format: ImageFormat = Field(default=ImageFormat.PNG, description="图片格式")

    # 规格信息
    width: int = Field(default=1024, description="宽度(像素)")
    height: int = Field(default=1024, description="高度(像素)")
    file_size: int | None = Field(default=None, description="文件大小(字节)")

    # 生成参数
    model: str | None = Field(default=None, description="生成模型")
    seed: int | None = Field(default=None, description="随机种子")
    style: str | None = Field(default=None, description="风格")

    # 状态信息
    status: AssetStatus = Field(default=AssetStatus.PENDING, description="状态")
    error_message: str | None = Field(default=None, description="错误信息")

    # 时间戳
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间"
    )
    completed_at: datetime | None = Field(default=None, description="完成时间")

    # 元数据
    metadata: dict = Field(default_factory=dict, description="额外元数据")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image_id": "img_001",
                    "image_type": "main",
                    "prompt": "Product photography of smart watch",
                    "url": "https://example.com/images/img_001.png",
                    "width": 1024,
                    "height": 1024,
                    "status": "completed",
                }
            ]
        }
    }

    @property
    def aspect_ratio(self) -> str:
        """计算宽高比。

        Returns:
            宽高比字符串。
        """
        from math import gcd

        g = gcd(self.width, self.height)
        return f"{self.width // g}:{self.height // g}"

    def is_ready(self) -> bool:
        """检查资源是否可用。

        Returns:
            是否可用。
        """
        return self.status == AssetStatus.COMPLETED and (
            self.url is not None or self.local_path is not None
        )


class GeneratedVideo(BaseModel):
    """生成的视频资源。"""

    # 基本信息
    video_id: str = Field(..., description="视频ID")
    title: str | None = Field(default=None, description="视频标题")

    # 生成信息
    storyboard_id: str | None = Field(default=None, description="分镜脚本ID")
    visual_prompt: str | None = Field(default=None, description="视觉提示词")

    # 资源信息
    url: str | None = Field(default=None, description="视频URL")
    local_path: str | None = Field(default=None, description="本地存储路径")
    format: VideoFormat = Field(default=VideoFormat.MP4, description="视频格式")

    # 规格信息
    width: int = Field(default=1920, description="宽度(像素)")
    height: int = Field(default=1080, description="高度(像素)")
    duration: float = Field(..., description="时长(秒)")
    fps: int = Field(default=30, description="帧率")
    file_size: int | None = Field(default=None, description="文件大小(字节)")

    # 生成参数
    model: str | None = Field(default=None, description="生成模型")
    style: str | None = Field(default=None, description="风格")

    # 状态信息
    status: AssetStatus = Field(default=AssetStatus.PENDING, description="状态")
    progress: float = Field(default=0.0, description="生成进度(0-100)")
    error_message: str | None = Field(default=None, description="错误信息")

    # 时间戳
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间"
    )
    completed_at: datetime | None = Field(default=None, description="完成时间")

    # 元数据
    metadata: dict = Field(default_factory=dict, description="额外元数据")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "video_id": "vid_001",
                    "title": "智能手表产品视频",
                    "url": "https://example.com/videos/vid_001.mp4",
                    "width": 1920,
                    "height": 1080,
                    "duration": 30.0,
                    "status": "completed",
                }
            ]
        }
    }

    @property
    def resolution(self) -> str:
        """获取分辨率描述。

        Returns:
            分辨率字符串。
        """
        if self.height >= 2160:
            return "4K"
        elif self.height >= 1440:
            return "2K"
        elif self.height >= 1080:
            return "1080p"
        elif self.height >= 720:
            return "720p"
        else:
            return f"{self.height}p"

    def is_ready(self) -> bool:
        """检查资源是否可用。

        Returns:
            是否可用。
        """
        return self.status == AssetStatus.COMPLETED and (
            self.url is not None or self.local_path is not None
        )


class QualityScore(BaseModel):
    """质量评分。"""

    overall_score: float = Field(..., description="总体评分", ge=0, le=1)
    clarity_score: float = Field(default=0.8, description="清晰度评分", ge=0, le=1)
    composition_score: float = Field(
        default=0.8, description="构图评分", ge=0, le=1
    )
    color_score: float = Field(default=0.8, description="色彩评分", ge=0, le=1)
    relevance_score: float = Field(
        default=0.8, description="相关性评分", ge=0, le=1
    )

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

    def is_acceptable(self, threshold: float = 0.7) -> bool:
        """检查是否达到可接受标准。

        Args:
            threshold: 阈值。

        Returns:
            是否可接受。
        """
        return self.overall_score >= threshold


class QualityIssue(BaseModel):
    """质量问题。"""

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


class QualityReport(BaseModel):
    """质量审核报告。"""

    asset_id: str = Field(..., description="资源ID")
    asset_type: str = Field(..., description="资源类型: image/video")

    # 评分
    score: QualityScore = Field(..., description="质量评分")

    # 问题列表
    issues: list[QualityIssue] = Field(
        default_factory=list, description="问题列表"
    )

    # 审核结果
    passed: bool = Field(..., description="是否通过")
    review_comments: str | None = Field(default=None, description="审核意见")

    # 时间戳
    reviewed_at: datetime = Field(
        default_factory=datetime.now, description="审核时间"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "asset_id": "img_001",
                    "asset_type": "image",
                    "score": {"overall_score": 0.92},
                    "issues": [],
                    "passed": True,
                }
            ]
        }
    }


class AssetCollection(BaseModel):
    """资源集合。"""

    # 基本信息
    collection_id: str = Field(..., description="集合ID")
    task_id: str = Field(..., description="任务ID")
    product_name: str = Field(..., description="商品名称")

    # 图片资源
    images: list[GeneratedImage] = Field(
        default_factory=list, description="图片列表"
    )

    # 视频资源
    videos: list[GeneratedVideo] = Field(
        default_factory=list, description="视频列表"
    )

    # 质量报告
    quality_reports: list[QualityReport] = Field(
        default_factory=list, description="质量报告列表"
    )

    # 时间戳
    created_at: datetime = Field(
        default_factory=datetime.now, description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="更新时间"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "collection_id": "col_001",
                    "task_id": "task_001",
                    "product_name": "智能手表",
                    "images": [],
                    "videos": [],
                }
            ]
        }
    }

    def add_image(self, image: GeneratedImage) -> None:
        """添加图片资源。

        Args:
            image: 图片对象。
        """
        self.images.append(image)
        self.updated_at = datetime.now()

    def add_video(self, video: GeneratedVideo) -> None:
        """添加视频资源。

        Args:
            video: 视频对象。
        """
        self.videos.append(video)
        self.updated_at = datetime.now()

    def get_completed_images(self) -> list[GeneratedImage]:
        """获取已完成的图片。

        Returns:
            已完成的图片列表。
        """
        return [img for img in self.images if img.is_ready()]

    def get_completed_videos(self) -> list[GeneratedVideo]:
        """获取已完成的视频。

        Returns:
            已完成的视频列表。
        """
        return [vid for vid in self.videos if vid.is_ready()]

    def get_overall_quality_score(self) -> float | None:
        """获取总体质量评分。

        Returns:
            平均质量评分，无报告则返回 None。
        """
        if not self.quality_reports:
            return None
        scores = [report.score.overall_score for report in self.quality_reports]
        return sum(scores) / len(scores)
