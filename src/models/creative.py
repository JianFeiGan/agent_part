"""
创意方案模型。

Description:
    定义创意策划相关的数据结构，包括创意方案、配色方案、视觉风格等。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from enum import Enum

from pydantic import BaseModel, Field


class VisualStyle(str, Enum):
    """视觉风格枚举。"""

    MINIMALIST = "minimalist"  # 极简风格
    MODERN = "modern"  # 现代风格
    VINTAGE = "vintage"  # 复古风格
    LUXURY = "luxury"  # 奢华风格
    TECH = "tech"  # 科技风格
    NATURAL = "natural"  # 自然风格
    PLAYFUL = "playful"  # 活泼风格
    PROFESSIONAL = "professional"  # 专业风格


class ImageType(str, Enum):
    """图片类型枚举。"""

    MAIN = "main"  # 主图
    SCENE = "scene"  # 场景图
    SELLING_POINT = "selling_point"  # 卖点图
    DETAIL = "detail"  # 详情图
    LIFESTYLE = "lifestyle"  # 生活方式图
    INFOGRAPHIC = "infographic"  # 信息图


class ColorRole(str, Enum):
    """颜色角色枚举。"""

    PRIMARY = "primary"  # 主色
    SECONDARY = "secondary"  # 辅助色
    ACCENT = "accent"  # 强调色
    BACKGROUND = "background"  # 背景色
    TEXT = "text"  # 文字色


class ColorInfo(BaseModel):
    """颜色信息。"""

    hex: str = Field(..., description="十六进制颜色值", pattern=r"^#[0-9A-Fa-f]{6}$")
    name: str = Field(..., description="颜色名称")
    role: ColorRole = Field(..., description="颜色角色")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"hex": "#FF6B35", "name": "活力橙", "role": "primary"},
                {"hex": "#2D3436", "name": "深灰", "role": "text"},
            ]
        }
    }


class ColorPalette(BaseModel):
    """配色方案。"""

    name: str = Field(..., description="配色方案名称")
    description: str = Field(..., description="配色方案描述")
    colors: list[ColorInfo] = Field(..., description="颜色列表")
    mood: str = Field(..., description="配色情绪/氛围")
    suitable_categories: list[str] = Field(
        default_factory=list, description="适用的商品类目"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "科技蓝",
                    "description": "专业、科技感的蓝色调配色",
                    "colors": [
                        {"hex": "#0066CC", "name": "科技蓝", "role": "primary"},
                        {"hex": "#E8F4FC", "name": "浅蓝背景", "role": "background"},
                        {"hex": "#333333", "name": "深灰文字", "role": "text"},
                    ],
                    "mood": "专业、科技、可靠",
                    "suitable_categories": ["digital", "sports"],
                }
            ]
        }
    }

    def get_color_by_role(self, role: ColorRole) -> ColorInfo | None:
        """根据角色获取颜色。

        Args:
            role: 颜色角色。

        Returns:
            对应的颜色信息，不存在则返回 None。
        """
        for color in self.colors:
            if color.role == role:
                return color
        return None

    def get_hex_colors(self) -> list[str]:
        """获取所有十六进制颜色值。

        Returns:
            颜色值列表。
        """
        return [color.hex for color in self.colors]


class ImagePrompt(BaseModel):
    """图片生成提示词。"""

    image_type: ImageType = Field(..., description="图片类型")
    prompt: str = Field(..., description="生成提示词")
    negative_prompt: str | None = Field(default=None, description="负向提示词")
    style_keywords: list[str] = Field(default_factory=list, description="风格关键词")
    aspect_ratio: str = Field(default="1:1", description="宽高比")
    quality: str = Field(default="standard", description="质量等级")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "image_type": "main",
                    "prompt": "Professional product photography of a smart watch, "
                    "clean white background, studio lighting, "
                    "high detail, 4k quality",
                    "negative_prompt": "blurry, low quality, watermark",
                    "style_keywords": ["professional", "clean", "minimalist"],
                    "aspect_ratio": "1:1",
                    "quality": "hd",
                }
            ]
        }
    }


class CreativePlan(BaseModel):
    """创意方案模型。"""

    # 基本信息
    plan_id: str | None = Field(default=None, description="方案ID")
    name: str = Field(..., description="创意主题名称")
    description: str = Field(..., description="创意方案描述")

    # 视觉风格
    visual_style: VisualStyle = Field(..., description="视觉风格")
    style_keywords: list[str] = Field(default_factory=list, description="风格关键词")

    # 配色方案
    color_palette: ColorPalette = Field(..., description="配色方案")

    # 图片提示词
    image_prompts: list[ImagePrompt] = Field(
        default_factory=list, description="图片生成提示词列表"
    )

    # 创意元素
    key_elements: list[str] = Field(
        default_factory=list, description="关键视觉元素"
    )
    composition_notes: str | None = Field(
        default=None, description="构图建议"
    )

    # 目标情感
    target_emotion: str | None = Field(default=None, description="目标情感")

    # 参考风格
    reference_styles: list[str] = Field(
        default_factory=list, description="参考风格/品牌"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "科技感极简风",
                    "description": "突出产品科技属性，采用简洁构图和冷色调",
                    "visual_style": "tech",
                    "style_keywords": ["科技感", "极简", "未来感"],
                    "color_palette": {
                        "name": "科技蓝",
                        "description": "专业科技感配色",
                        "colors": [
                            {"hex": "#0066CC", "name": "科技蓝", "role": "primary"}
                        ],
                        "mood": "专业科技",
                    },
                    "key_elements": ["产品特写", "光影效果", "几何元素"],
                    "target_emotion": "信赖感、科技感",
                }
            ]
        }
    }

    def get_prompt_by_type(self, image_type: ImageType) -> ImagePrompt | None:
        """根据图片类型获取提示词。

        Args:
            image_type: 图片类型。

        Returns:
            对应的图片提示词，不存在则返回 None。
        """
        for prompt in self.image_prompts:
            if prompt.image_type == image_type:
                return prompt
        return None

    def add_image_prompt(self, prompt: ImagePrompt) -> None:
        """添加图片提示词。

        Args:
            prompt: 图片提示词对象。
        """
        # 如果已存在同类型的提示词，则替换
        existing = self.get_prompt_by_type(prompt.image_type)
        if existing:
            self.image_prompts.remove(existing)
        self.image_prompts.append(prompt)
