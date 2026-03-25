"""
商品 DTO 模型。

Description:
    定义商品相关的 API 请求和响应模型。
@author ganjianfei
@version 1.0.0
2026-03-25
"""

from pydantic import BaseModel, Field

from src.models.product import (
    ProductCategory,
    ProductSpec,
    SellingPoint,
    SellingPointType,
)


class ProductCreateRequest(BaseModel):
    """创建商品请求模型。

    用于创建新商品的 API 请求体。

    Attributes:
        name: 商品名称。
        brand: 品牌名称。
        category: 商品类目。
        subcategory: 子类目。
        description: 商品描述。
        short_description: 短描述。
        selling_points: 卖点列表。
        specifications: 规格列表。
        target_audience: 目标人群标签。
        price_range: 价格区间。
        existing_images: 已有图片URL列表。
        existing_videos: 已有视频URL列表。
        tags: 标签列表。
    """

    name: str = Field(..., description="商品名称", min_length=2, max_length=100)
    brand: str | None = Field(default=None, description="品牌名称", max_length=50)
    category: ProductCategory = Field(..., description="商品类目")
    subcategory: str | None = Field(default=None, description="子类目", max_length=50)
    description: str = Field(..., description="商品描述", min_length=10, max_length=2000)
    short_description: str | None = Field(
        default=None, description="短描述，用于图片文案", max_length=100
    )
    selling_points: list[SellingPoint] = Field(
        default_factory=list, description="卖点列表"
    )
    specifications: list[ProductSpec] = Field(
        default_factory=list, description="规格列表"
    )
    target_audience: list[str] = Field(
        default_factory=list, description="目标人群标签", max_length=20
    )
    price_range: tuple[float, float] | None = Field(
        default=None, description="价格区间 (最低价, 最高价)"
    )
    existing_images: list[str] = Field(
        default_factory=list, description="已有图片URL列表"
    )
    existing_videos: list[str] = Field(
        default_factory=list, description="已有视频URL列表"
    )
    tags: list[str] = Field(default_factory=list, description="标签列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "智能运动手表",
                    "brand": "TechFit",
                    "category": "digital",
                    "description": "一款集健康监测、运动追踪、智能提醒于一体的高性价比智能手表，支持心率监测、血氧检测、睡眠分析等功能。",
                    "selling_points": [
                        {
                            "title": "全天候健康监测",
                            "description": "24小时心率监测，血氧检测，睡眠质量分析",
                            "point_type": "functional",
                            "priority": 5,
                            "keywords": ["健康", "心率", "血氧"],
                        }
                    ],
                    "target_audience": ["运动爱好者", "上班族", "健康关注者"],
                    "price_range": [299.0, 599.0],
                }
            ]
        }
    }


class ProductUpdateRequest(BaseModel):
    """更新商品请求模型。

    用于更新商品信息的 API 请求体。所有字段均为可选。

    Attributes:
        name: 商品名称。
        brand: 品牌名称。
        category: 商品类目。
        subcategory: 子类目。
        description: 商品描述。
        short_description: 短描述。
        selling_points: 卖点列表。
        specifications: 规格列表。
        target_audience: 目标人群标签。
        price_range: 价格区间。
        existing_images: 已有图片URL列表。
        existing_videos: 已有视频URL列表。
        tags: 标签列表。
    """

    name: str | None = Field(default=None, description="商品名称", min_length=2, max_length=100)
    brand: str | None = Field(default=None, description="品牌名称", max_length=50)
    category: ProductCategory | None = Field(default=None, description="商品类目")
    subcategory: str | None = Field(default=None, description="子类目", max_length=50)
    description: str | None = Field(
        default=None, description="商品描述", min_length=10, max_length=2000
    )
    short_description: str | None = Field(
        default=None, description="短描述，用于图片文案", max_length=100
    )
    selling_points: list[SellingPoint] | None = Field(
        default=None, description="卖点列表"
    )
    specifications: list[ProductSpec] | None = Field(
        default=None, description="规格列表"
    )
    target_audience: list[str] | None = Field(
        default=None, description="目标人群标签"
    )
    price_range: tuple[float, float] | None = Field(
        default=None, description="价格区间 (最低价, 最高价)"
    )
    existing_images: list[str] | None = Field(
        default=None, description="已有图片URL列表"
    )
    existing_videos: list[str] | None = Field(
        default=None, description="已有视频URL列表"
    )
    tags: list[str] | None = Field(default=None, description="标签列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "智能运动手表 Pro",
                    "description": "升级版智能运动手表，新增GPS定位功能。",
                }
            ]
        }
    }


class ProductResponse(BaseModel):
    """商品响应模型。

    用于商品信息的 API 响应。

    Attributes:
        product_id: 商品ID。
        name: 商品名称。
        brand: 品牌名称。
        category: 商品类目。
        subcategory: 子类目。
        description: 商品描述。
        short_description: 短描述。
        selling_points: 卖点列表。
        specifications: 规格列表。
        target_audience: 目标人群标签。
        price_range: 价格区间。
        existing_images: 已有图片URL列表。
        existing_videos: 已有视频URL列表。
        tags: 标签列表。
    """

    product_id: str = Field(..., description="商品ID")
    name: str = Field(..., description="商品名称")
    brand: str | None = Field(default=None, description="品牌名称")
    category: ProductCategory = Field(..., description="商品类目")
    subcategory: str | None = Field(default=None, description="子类目")
    description: str = Field(..., description="商品描述")
    short_description: str | None = Field(default=None, description="短描述")
    selling_points: list[SellingPoint] = Field(
        default_factory=list, description="卖点列表"
    )
    specifications: list[ProductSpec] = Field(
        default_factory=list, description="规格列表"
    )
    target_audience: list[str] = Field(
        default_factory=list, description="目标人群标签"
    )
    price_range: tuple[float, float] | None = Field(
        default=None, description="价格区间 (最低价, 最高价)"
    )
    existing_images: list[str] = Field(
        default_factory=list, description="已有图片URL列表"
    )
    existing_videos: list[str] = Field(
        default_factory=list, description="已有视频URL列表"
    )
    tags: list[str] = Field(default_factory=list, description="标签列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_id": "prod_001",
                    "name": "智能运动手表",
                    "brand": "TechFit",
                    "category": "digital",
                    "description": "一款集健康监测、运动追踪、智能提醒于一体的高性价比智能手表。",
                    "selling_points": [
                        {
                            "title": "全天候健康监测",
                            "description": "24小时心率监测，血氧检测，睡眠质量分析",
                            "point_type": "functional",
                            "priority": 5,
                            "keywords": ["健康", "心率", "血氧"],
                        }
                    ],
                    "target_audience": ["运动爱好者", "上班族", "健康关注者"],
                    "price_range": [299.0, 599.0],
                }
            ]
        }
    }


class ProductListQuery(BaseModel):
    """商品列表查询参数模型。

    用于商品列表查询接口的请求参数。

    Attributes:
        name: 商品名称（模糊查询）。
        brand: 品牌名称。
        category: 商品类目。
        tag: 标签。
        page: 页码。
        page_size: 每页大小。
    """

    name: str | None = Field(default=None, description="商品名称（模糊查询）")
    brand: str | None = Field(default=None, description="品牌名称")
    category: ProductCategory | None = Field(default=None, description="商品类目")
    tag: str | None = Field(default=None, description="标签")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=10, ge=1, le=100, description="每页大小")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "手表", "category": "digital", "page": 1, "page_size": 10}
            ]
        }
    }