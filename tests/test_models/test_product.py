"""
测试商品模型。

Tests for Product, SellingPoint, and related models.
"""


from src.models.product import (
    Product,
    ProductCategory,
    ProductSpec,
    SellingPoint,
    SellingPointType,
)


class TestSellingPoint:
    """测试卖点模型。"""

    def test_create_selling_point(self) -> None:
        """测试创建卖点。"""
        point = SellingPoint(
            title="超长续航",
            description="续航时间长达7天",
            point_type=SellingPointType.FUNCTIONAL,
            priority=5,
            keywords=["续航", "省电"],
        )
        assert point.title == "超长续航"
        assert point.priority == 5

    def test_selling_point_defaults(self) -> None:
        """测试卖点默认值。"""
        point = SellingPoint(
            title="测试卖点",
            description="测试描述内容",
        )
        assert point.point_type == SellingPointType.FUNCTIONAL
        assert point.priority == 1
        assert point.keywords == []


class TestProduct:
    """测试商品模型。"""

    def test_create_product(self) -> None:
        """测试创建商品。"""
        product = Product(
            name="智能手表",
            category=ProductCategory.DIGITAL,
            description="一款智能运动手表，支持健康监测",
        )
        assert product.name == "智能手表"
        assert product.category == ProductCategory.DIGITAL

    def test_product_with_selling_points(self) -> None:
        """测试带卖点的商品。"""
        points = [
            SellingPoint(
                title="长续航",
                description="续航时间长达7天",
                priority=5,
            ),
            SellingPoint(
                title="防水",
                description="IP68级防水设计",
                priority=4,
            ),
        ]
        product = Product(
            name="智能手表",
            category=ProductCategory.DIGITAL,
            description="一款智能运动手表，功能齐全",
            selling_points=points,
        )
        assert len(product.selling_points) == 2

    def test_get_main_selling_points(self) -> None:
        """测试获取主要卖点。"""
        points = [
            SellingPoint(title="卖点1", description="这是一个卖点描述", priority=5),
            SellingPoint(title="卖点2", description="这是另一个卖点描述", priority=3),
            SellingPoint(title="卖点3", description="这是第三个卖点描述", priority=4),
        ]
        product = Product(
            name="测试商品",
            category=ProductCategory.DIGITAL,
            description="测试商品描述内容较多字数",
            selling_points=points,
        )
        main_points = product.get_main_selling_points(limit=2)
        assert len(main_points) == 2
        assert main_points[0].priority >= main_points[1].priority

    def test_get_keywords(self) -> None:
        """测试获取关键词。"""
        product = Product(
            name="测试商品",
            category=ProductCategory.DIGITAL,
            description="测试商品描述内容较多字数",
            tags=["智能", "科技"],
            selling_points=[
                SellingPoint(
                    title="卖点1",
                    description="功能特性描述",
                    keywords=["功能", "特性"],
                ),
            ],
        )
        keywords = product.get_keywords()
        assert "智能" in keywords
        assert "功能" in keywords


class TestProductSpec:
    """测试商品规格。"""

    def test_create_spec(self) -> None:
        """测试创建规格。"""
        spec = ProductSpec(name="重量", value="150", unit="g")
        assert spec.name == "重量"
        assert spec.value == "150"
        assert spec.unit == "g"
