"""
刊登工具数据模型。

定义刊登商品、任务、素材包、文案包的 Pydantic 模型。

Description:
    刊登工具的独立数据模型，与现有 Product 模型解耦，
    支持从外部系统导入商品并生成刊登素材和文案。
@author ganjianfei
@version 1.0.0
2026-04-25
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Platform(str, Enum):
    """目标电商平台。"""

    AMAZON = "amazon"
    EBAY = "ebay"
    SHOPIFY = "shopify"


class TaskStatus(str, Enum):
    """刊登任务状态。"""

    PENDING = "pending"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    PUSHING = "pushing"
    COMPLETED = "completed"
    FAILED = "failed"


class ImageRef(BaseModel):
    """图片引用。"""

    url: str = Field(..., description="图片URL或本地路径")
    is_main: bool = Field(default=False, description="是否为主图")
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    file_size: int | None = Field(default=None, ge=0)


class ListingProduct(BaseModel):
    """标准化刊登商品。

    与平台无关的商品信息模型，用于刊登流程的输入。
    """

    id: int | None = Field(default=None, description="主键ID")
    sku: str = Field(..., min_length=1, max_length=100, description="商品SKU")
    title: str = Field(..., min_length=1, max_length=500, description="商品标题")
    description: str | None = Field(default=None, description="商品描述")
    category: str | None = Field(default=None, description="商品类目")
    brand: str | None = Field(default=None, description="品牌")
    price: Decimal | None = Field(default=None, description="价格")
    weight: Decimal | None = Field(default=None, description="重量(kg)")
    dimensions: dict[str, Any] | None = Field(default=None, description="尺寸信息")
    source_images: list[ImageRef] = Field(default_factory=list, description="原始图片素材")
    attributes: dict[str, Any] = Field(default_factory=dict, description="平台特有属性")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "sku": "BT-HP-001",
                    "title": "Wireless Bluetooth Headphones",
                    "description": "High-quality wireless headphones",
                    "category": "Electronics",
                    "brand": "SoundMax",
                    "price": "49.99",
                    "weight": "0.35",
                    "dimensions": {"length": 20, "width": 18, "height": 8, "unit": "cm"},
                    "source_images": [],
                    "attributes": {"color": "Black"},
                }
            ]
        }
    }

    @property
    def main_image(self) -> ImageRef | None:
        """获取主图引用。"""
        for img in self.source_images:
            if img.is_main:
                return img
        return self.source_images[0] if self.source_images else None


class AssetPackage(BaseModel):
    """平台标准化素材包。"""

    id: int | None = Field(default=None)
    listing_task_id: int = Field(..., description="关联任务ID")
    platform: Platform = Field(..., description="目标平台")
    main_image: str | None = Field(default=None, description="主图URL")
    variant_images: list[str] = Field(default_factory=list, description="变体图URL列表")
    video_url: str | None = Field(default=None, description="视频URL")
    a_plus_images: list[str] = Field(default_factory=list, description="A+页面图片")


class CopywritingPackage(BaseModel):
    """平台标准化文案包。"""

    id: int | None = Field(default=None)
    listing_task_id: int = Field(..., description="关联任务ID")
    platform: Platform = Field(..., description="目标平台")
    language: str = Field(default="en", description="语言代码")
    title: str = Field(default="", description="平台优化标题")
    bullet_points: list[str] = Field(default_factory=list, description="五点描述")
    description: str = Field(default="", description="长描述")
    search_terms: list[str] = Field(default_factory=list, description="搜索关键词")


class ListingTask(BaseModel):
    """刊登任务。"""

    id: int | None = Field(default=None)
    product_id: int = Field(..., description="关联商品ID")
    target_platforms: list[Platform] = Field(default_factory=list)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)

    def mark_generating(self) -> None:
        """标记为生成中。"""
        self.status = TaskStatus.GENERATING

    def mark_completed(self) -> None:
        """标记为完成。"""
        self.status = TaskStatus.COMPLETED

    def mark_failed(self, error: str | None = None) -> None:
        """标记为失败。"""
        self.status = TaskStatus.FAILED
        if error:
            self.results["error"] = error