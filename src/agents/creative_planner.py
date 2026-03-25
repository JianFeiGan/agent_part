"""
创意策划Agent模块。

Description:
    负责设计创意主题和视觉风格。
    主要功能：
    - 创意主题生成
    - 视觉风格确定
    - 配色方案设计
    - 构图方案规划
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.models.creative import (
    ColorInfo,
    ColorPalette,
    ColorRole,
    CreativePlan,
    VisualStyle,
)

# 预设配色方案
PRESET_PALETTES: dict[str, dict[str, Any]] = {
    "tech": {
        "name": "科技蓝",
        "colors": [
            {"hex": "#0066CC", "name": "科技蓝", "role": "primary"},
            {"hex": "#E8F4FC", "name": "浅蓝背景", "role": "background"},
            {"hex": "#333333", "name": "深灰文字", "role": "text"},
            {"hex": "#FF6B35", "name": "活力橙", "role": "accent"},
        ],
        "mood": "专业、科技、可靠",
    },
    "nature": {
        "name": "自然绿",
        "colors": [
            {"hex": "#4CAF50", "name": "自然绿", "role": "primary"},
            {"hex": "#F5F5DC", "name": "米白背景", "role": "background"},
            {"hex": "#2E7D32", "name": "深绿文字", "role": "text"},
        ],
        "mood": "自然、健康、清新",
    },
    "luxury": {
        "name": "奢华金",
        "colors": [
            {"hex": "#D4AF37", "name": "奢华金", "role": "primary"},
            {"hex": "#1A1A1A", "name": "深黑背景", "role": "background"},
            {"hex": "#FFFFFF", "name": "白色文字", "role": "text"},
        ],
        "mood": "高端、奢华、尊贵",
    },
    "minimalist": {
        "name": "极简白",
        "colors": [
            {"hex": "#FFFFFF", "name": "纯白", "role": "primary"},
            {"hex": "#F5F5F5", "name": "浅灰背景", "role": "background"},
            {"hex": "#333333", "name": "深灰文字", "role": "text"},
        ],
        "mood": "简约、现代、清晰",
    },
}


class CreativePlannerAgent(BaseAgent[AgentState]):
    """创意策划Agent。

    根据需求分析结果，设计创意方案。

    Example:
        >>> agent = CreativePlannerAgent()
        >>> result = await agent.execute(state)
        >>> plan = result.data.get("creative_plan")
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化创意策划Agent。"""
        super().__init__(role=AgentRole.CREATIVE_PLANNER, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 创意主题生成提示
        creative_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个电商视觉创意专家。"
                    "请根据商品特性和卖点，设计创意主题方案。\n\n"
                    "输出JSON格式，包含：\n"
                    "- theme_name: 创意主题名称\n"
                    "- theme_description: 主题描述\n"
                    "- visual_style: 视觉风格（tech/modern/minimalist/luxury/natural/playful）\n"
                    "- style_keywords: 风格关键词列表\n"
                    "- key_elements: 关键视觉元素\n"
                    "- target_emotion: 目标情感\n"
                    "- color_suggestion: 推荐配色方案名称",
                ),
                (
                    "human",
                    "商品信息：{product_info}\n"
                    "需求报告：{requirement_report}\n"
                    "风格偏好：{style_preference}\n\n"
                    "请设计创意方案。",
                ),
            ]
        )
        self.register_prompt("creative", creative_prompt)

        # 配色方案推荐提示
        color_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个色彩搭配专家。"
                    "请为商品推荐最适合的配色方案。\n\n"
                    "考虑因素：\n"
                    "- 商品类目特点\n"
                    "- 目标人群偏好\n"
                    "- 品牌调性\n"
                    "- 流行趋势",
                ),
                (
                    "human",
                    "商品类目：{category}\n"
                    "目标人群：{target_audience}\n"
                    "风格定位：{style}\n\n"
                    "推荐配色方案。",
                ),
            ]
        )
        self.register_prompt("color", color_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行创意策划。

        Args:
            state: 当前状态。

        Returns:
            包含创意方案的结果。
        """
        try:
            product = state.product_info
            report = state.requirement_report

            if product is None:
                return AgentResult(
                    success=False,
                    error="缺少商品信息",
                )

            # 生成创意方案
            creative_plan = await self._generate_creative_plan(product, report, state)

            # 更新状态
            state.creative_plan = creative_plan
            state.color_palette = creative_plan.color_palette.model_dump()
            state.mark_step_completed("creative_planning")

            return AgentResult(
                success=True,
                data={
                    "creative_plan": creative_plan.model_dump(),
                    "color_palette": creative_plan.color_palette.model_dump(),
                },
                next_agent=AgentRole.VISUAL_DESIGNER,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"创意策划失败: {e}",
            )

    async def _generate_creative_plan(
        self,
        product: Any,
        report: Any,
        state: AgentState,
    ) -> CreativePlan:
        """生成创意方案。

        Args:
            product: 商品信息。
            report: 需求报告。
            state: 当前状态。

        Returns:
            创意方案。
        """
        # 准备输入
        product_info = f"{product.name} - {product.description[:100]}"
        requirement_report = report.model_dump_json() if report else "{}"
        style_preference = (
            state.generation_request.style_preference if state.generation_request else None
        ) or "自动推荐"

        # 调用LLM
        prompt = self.get_prompt("creative")
        if prompt:
            response = await self.invoke_llm(
                prompt,
                {
                    "product_info": product_info,
                    "requirement_report": requirement_report,
                    "style_preference": style_preference,
                },
            )
            return self._parse_creative_response(response, product)

        # 默认方案
        return self._create_default_plan(product)

    def _parse_creative_response(self, response: str, product: Any) -> CreativePlan:
        """解析创意响应。

        Args:
            response: LLM响应。
            product: 商品信息。

        Returns:
            创意方案。
        """
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])

                # 确定视觉风格
                style_str = data.get("visual_style", "modern").upper()
                try:
                    visual_style = VisualStyle[style_str]
                except KeyError:
                    visual_style = VisualStyle.MODERN

                # 获取配色方案
                color_name = data.get("color_suggestion", "tech")
                palette = self._get_palette(color_name)

                return CreativePlan(
                    name=data.get("theme_name", "默认创意主题"),
                    description=data.get("theme_description", ""),
                    visual_style=visual_style,
                    style_keywords=data.get("style_keywords", []),
                    color_palette=palette,
                    key_elements=data.get("key_elements", []),
                    target_emotion=data.get("target_emotion"),
                )
        except json.JSONDecodeError:
            pass

        return self._create_default_plan(product)

    def _get_palette(self, name: str) -> ColorPalette:
        """获取配色方案。

        Args:
            name: 方案名称。

        Returns:
            配色方案。
        """
        preset = PRESET_PALETTES.get(name, PRESET_PALETTES["tech"])
        colors = [
            ColorInfo(
                hex=c["hex"],
                name=c["name"],
                role=ColorRole(c["role"]),
            )
            for c in preset["colors"]
        ]
        return ColorPalette(
            name=preset["name"],
            description=f"{preset['name']}配色方案",
            colors=colors,
            mood=preset["mood"],
        )

    def _create_default_plan(self, product: Any) -> CreativePlan:
        """创建默认创意方案。

        Args:
            product: 商品信息。

        Returns:
            默认创意方案。
        """
        # 根据类目选择配色
        category = (
            product.category.value if hasattr(product.category, "value") else str(product.category)
        )
        palette_name = "tech"  # 默认科技风
        if category in ["clothing", "beauty"]:
            palette_name = "minimalist"
        elif category in ["food", "home"]:
            palette_name = "nature"
        elif "luxury" in product.name.lower():
            palette_name = "luxury"

        return CreativePlan(
            name=f"{product.name}产品展示",
            description="专业产品展示方案",
            visual_style=VisualStyle.MODERN,
            style_keywords=["专业", "现代", "简洁"],
            color_palette=self._get_palette(palette_name),
            key_elements=["产品特写", "场景展示", "细节呈现"],
            target_emotion="信赖感、品质感",
        )
