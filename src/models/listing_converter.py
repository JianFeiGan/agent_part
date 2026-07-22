"""视觉生成商品模型到刊登商品模型的转换器。

Description:
    将视觉生成工作流使用的 Product 模型转换为刊登工作流使用的
    ListingProduct 模型，并记录 source_product_id 以便后续从资产库
    拉取 AI 生成图片。
@author ganjianfei
@version 1.0.0
2026-07-22
"""

from src.models.listing import ListingProduct
from src.models.product import Product


def product_to_listing(product: Product) -> ListingProduct:
    """将视觉生成商品转换为刊登商品。

    转换规则:
        - sku: 优先用 product_id，无则用 name 哈希生成（VIS- 前缀）
        - title: product.name
        - description: product.description
        - category: product.category.value
        - brand: product.brand
        - source_images: 留空，由 ListingAssetLoader 后续填充
        - attributes.source_product_id: product.product_id（存在时）

    Args:
        product: 视觉生成商品模型。

    Returns:
        登记商品模型。
    """
    if product.product_id:
        sku = product.product_id
        attributes: dict = {"source_product_id": product.product_id}
    else:
        sku = f"VIS-{abs(hash(product.name)) % 100000:05d}"
        attributes = {}

    return ListingProduct(
        sku=sku,
        title=product.name,
        description=product.description,
        category=product.category.value if product.category else None,
        brand=product.brand,
        source_images=[],
        attributes=attributes,
    )
