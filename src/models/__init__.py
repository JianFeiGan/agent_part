"""
数据模型模块。

定义核心数据模型：
- Product: 商品信息
- CreativePlan: 创意方案
- Storyboard: 分镜脚本
- GeneratedAssets: 生成资源
"""

from src.models.assets import AssetCollection, GeneratedImage, GeneratedVideo
from src.models.creative import ColorPalette, CreativePlan, VisualStyle
from src.models.product import Product, ProductCategory, SellingPoint
from src.models.storyboard import Scene, Storyboard

__all__ = [
    "Product",
    "ProductCategory",
    "SellingPoint",
    "CreativePlan",
    "ColorPalette",
    "VisualStyle",
    "Storyboard",
    "Scene",
    "GeneratedImage",
    "GeneratedVideo",
    "AssetCollection",
]
