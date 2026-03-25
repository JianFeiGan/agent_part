"""
商品信息模型。

Description:
    定义商品相关的数据结构，包括商品信息、类目、卖点等。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from enum import Enum

from pydantic import BaseModel, Field


class ProductCategory(str, Enum):
    """商品类目枚举。"""

    DIGITAL = "digital"  # 数码产品
    CLOTHING = "clothing"  # 服装服饰
    FOOD = "food"  # 食品饮料
    BEAUTY = "beauty"  # 美妆护肤
    HOME = "home"  # 家居用品
    SPORTS = "sports"  # 运动户外
    BABY = "baby"  # 母婴用品
    PET = "pet"  # 宠物用品
    OTHER = "other"  # 其他


class SellingPointType(str, Enum):
    """卖点类型枚举。"""

    FUNCTIONAL = "functional"  # 功能卖点
    EMOTIONAL = "emotional"  # 情感卖点
    DIFFERENTIATION = "differentiation"  # 差异化卖点
    SCENARIO = "scenario"  # 场景卖点


class SellingPoint(BaseModel):
    """商品卖点。"""

    title: str = Field(..., description="卖点标题", min_length=2, max_length=50)
    description: str = Field(..., description="卖点详细描述", min_length=5, max_length=500)
    point_type: SellingPointType = Field(
        default=SellingPointType.FUNCTIONAL, description="卖点类型"
    )
    priority: int = Field(default=1, description="优先级，1-5，5最高", ge=1, le=5)
    keywords: list[str] = Field(default_factory=list, description="关键词列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "title": "超长续航",
                    "description": "续航时间长达7天，告别电量焦虑",
                    "point_type": "functional",
                    "priority": 5,
                    "keywords": ["续航", "省电", "长待机"],
                }
            ]
        }
    }


class ProductSpec(BaseModel):
    """商品规格。"""

    name: str = Field(..., description="规格名称")
    value: str = Field(..., description="规格值")
    unit: str | None = Field(default=None, description="单位")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "重量", "value": "150", "unit": "g"},
                {"name": "尺寸", "value": "10x5x2", "unit": "cm"},
            ]
        }
    }


class Product(BaseModel):
    """商品信息模型。"""

    # 基本信息
    product_id: str | None = Field(default=None, description="商品ID")
    name: str = Field(..., description="商品名称", min_length=2, max_length=100)
    brand: str | None = Field(default=None, description="品牌名称")
    category: ProductCategory = Field(..., description="商品类目")
    subcategory: str | None = Field(default=None, description="子类目")

    # 描述信息
    description: str = Field(..., description="商品描述", min_length=10, max_length=2000)
    short_description: str | None = Field(
        default=None, description="短描述，用于图片文案", max_length=100
    )

    # 卖点信息
    selling_points: list[SellingPoint] = Field(default_factory=list, description="卖点列表")

    # 规格信息
    specifications: list[ProductSpec] = Field(default_factory=list, description="规格列表")

    # 目标用户
    target_audience: list[str] = Field(default_factory=list, description="目标人群标签")

    # 价格区间
    price_range: tuple[float, float] | None = Field(
        default=None, description="价格区间 (最低价, 最高价)"
    )

    # 已有素材
    existing_images: list[str] = Field(default_factory=list, description="已有图片URL列表")
    existing_videos: list[str] = Field(default_factory=list, description="已有视频URL列表")

    # 元数据
    tags: list[str] = Field(default_factory=list, description="标签列表")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "product_id": "prod_001",
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

    def get_main_selling_points(self, limit: int = 3) -> list[SellingPoint]:
        """获取主要卖点。

        Args:
            limit: 返回数量限制。

        Returns:
            按优先级排序的主要卖点列表。
        """
        sorted_points = sorted(self.selling_points, key=lambda x: x.priority, reverse=True)
        return sorted_points[:limit]

    def get_keywords(self) -> list[str]:
        """获取所有关键词。

        Returns:
            合并去重后的关键词列表。
        """
        keywords = set(self.tags)
        for point in self.selling_points:
            keywords.update(point.keywords)
        return list(keywords)
