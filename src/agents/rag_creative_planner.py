"""
RAG增强的创意策划Agent模块。

Description:
    基于知识库检索的创意策划Agent，通过RAG增强创意主题和视觉风格设计。
    主要功能：
    - 品牌视觉规范指导的创意主题
    - 类目风格知识辅助的视觉设计
    - 历史成功案例参考的配色方案
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import logging
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import (
    CATEGORY_MEMORY_FALLBACK,
    AgentResult,
    AgentRole,
    AgentRuntimeState,
    BaseAgent,
)
from src.agents.llm_json import extract_json
from src.models.creative import (
    ColorInfo,
    ColorPalette,
    ColorRole,
    CreativePlan,
    VisualStyle,
)

logger = logging.getLogger(__name__)

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


class RAGEnhancedCreativePlanner(BaseAgent[AgentRuntimeState]):
    """RAG增强的创意策划Agent。

    通过知识库检索增强创意策划能力：
    - 品牌规范：遵循品牌视觉指南
    - 类目风格：匹配类目最佳实践
    - 成功案例：借鉴历史优质创意

    Example:
        >>> from src.rag.retriever import KnowledgeRetriever
        >>> retriever = KnowledgeRetriever()
        >>> agent = RAGEnhancedCreativePlanner(retriever=retriever)
        >>> result = await agent.execute(state, session)
    """

    def __init__(self, session: AsyncSession | None = None, **kwargs: Any) -> None:
        """初始化RAG增强创意策划Agent。

        Args:
            session: 数据库会话，用于知识检索。
            **kwargs: 传递给父类的参数。
        """
        super().__init__(role=AgentRole.CREATIVE_PLANNER, **kwargs)
        self._session = session
        self._setup_prompts()

    def set_session(self, session: AsyncSession) -> None:
        """设置数据库会话。

        Args:
            session: 数据库会话。
        """
        self._session = session

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # RAG增强的创意主题生成提示
        creative_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个电商视觉创意专家。"
                    "请根据商品特性和知识库参考信息，设计创意主题方案。\n\n"
                    "【品牌视觉规范】\n{brand_guidelines}\n\n"
                    "【类目风格参考】\n{category_styles}\n\n"
                    "【成功案例灵感】\n{case_inspirations}\n\n"
                    "【类目记忆】\n{category_memory_context}\n\n"
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
        self.register_prompt("rag_creative", creative_prompt)

        # 配色方案推荐提示
        color_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个色彩搭配专家。"
                    "请结合品牌色彩规范和商品特点，推荐最佳配色方案。\n\n"
                    "【品牌色彩规范】\n{brand_colors}\n\n"
                    "考虑因素：\n"
                    "- 品牌调性和色彩规范\n"
                    "- 商品类目特点\n"
                    "- 目标人群偏好\n"
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
        self.register_prompt("rag_color", color_prompt)

    async def execute(self, state: AgentRuntimeState) -> AgentResult:
        """执行RAG增强的创意策划。

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

            # RAG检索相关知识
            (
                brand_guidelines,
                category_styles,
                case_inspirations,
                rag_sources,
            ) = await self._retrieve_creative_knowledge(state)

            # 检索类目记忆（Graph RAG / CategoryMemory）
            category = (
                product.category.value
                if hasattr(product.category, "value")
                else str(product.category)
            )
            category_memory = await self._retrieve_category_memory_context(
                self._session, category
            )

            # 生成创意方案
            creative_plan = await self._generate_creative_plan_with_rag(
                product,
                report,
                state,
                brand_guidelines,
                category_styles,
                case_inspirations,
                category_memory,
            )

            # 更新状态
            state.creative_plan = creative_plan
            state.color_palette = creative_plan.color_palette.model_dump()
            state.mark_step_completed("creative_planning")

            return AgentResult(
                success=True,
                data={
                    "creative_plan": creative_plan.model_dump(),
                    "color_palette": creative_plan.color_palette.model_dump(),
                    "rag_enhanced": bool(brand_guidelines or category_styles or case_inspirations),
                    "rag_sources": rag_sources,
                },
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"创意策划失败: {e}",
            )

    async def _retrieve_creative_knowledge(
        self, state: "AgentRuntimeState"
    ) -> tuple[str, str, str, list[dict[str, Any]]]:
        """检索创意相关知识（领域方法：品牌规范+类目风格+成功案例）。

        Args:
            state: 当前状态。

        Returns:
            (品牌规范, 类目风格, 成功案例, RAG 来源列表) 四元组；
            检索失败时返回空上下文降级。
        """
        empty: tuple[str, str, str, list[dict[str, Any]]] = ("", "", "", [])
        if not self.has_rag() or not self._session:
            return empty

        product = state.product_info
        if not product:
            return empty

        from src.rag.retriever import KnowledgeRetriever

        if not isinstance(self._retriever, KnowledgeRetriever):
            return empty

        category = (
            product.category.value if hasattr(product.category, "value") else str(product.category)
        )
        style_preference = (
            state.generation_request.style_preference if state.generation_request else None
        )

        try:
            result = await self._retriever.retrieve_for_creative_planning(
                self._session,
                category=category,
                brand=product.brand or None,
                style_preference=style_preference,
                tenant_id=self._tenant_id,
            )
        except Exception as e:
            logger.warning("创意策划知识检索失败，按无知识降级: %s", e)
            return empty

        # 按文档类型分桶
        brand_parts: list[str] = []
        style_parts: list[str] = []
        case_parts: list[str] = []
        for r in result.results:
            if r.doc_type == "brand_guide":
                brand_parts.append(r.content[:400])
            elif r.doc_type == "category_knowledge":
                style_parts.append(r.content[:400])
            elif r.doc_type == "case_study":
                case_parts.append(r.content[:300])

        rag_sources = [
            {
                "query": result.query,
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "similarity": r.similarity,
            }
            for r in result.results
        ]
        state.rag_sources = rag_sources

        return (
            "\n".join(brand_parts[:2]),
            "\n".join(style_parts[:2]),
            "\n".join(case_parts[:2]),
            rag_sources,
        )

    async def _generate_creative_plan_with_rag(
        self,
        product: Any,
        report: Any,
        state: "AgentRuntimeState",
        brand_guidelines: str,
        category_styles: str,
        case_inspirations: str,
        category_memory: str = "",
    ) -> CreativePlan:
        """使用RAG知识生成创意方案。

        Args:
            product: 商品信息。
            report: 需求报告。
            state: 当前状态。
            brand_guidelines: 品牌规范。
            category_styles: 类目风格。
            case_inspirations: 成功案例。
            category_memory: 类目记忆上下文。

        Returns:
            创意方案。
        """
        product_info = f"{product.name} - {product.description[:100]}"
        requirement_report = report.model_dump_json() if report else "{}"
        style_preference = (
            state.generation_request.style_preference if state.generation_request else None
        ) or "自动推荐"

        prompt = self.get_prompt("rag_creative")
        if prompt:
            response = await self.invoke_llm(
                prompt,
                {
                    "brand_guidelines": brand_guidelines or "暂无品牌规范",
                    "category_styles": category_styles or "暂无类目风格参考",
                    "case_inspirations": case_inspirations or "暂无成功案例参考",
                    "category_memory_context": category_memory or CATEGORY_MEMORY_FALLBACK,
                    "product_info": product_info,
                    "requirement_report": requirement_report,
                    "style_preference": style_preference,
                },
            )
            return self._parse_creative_response(response, product, brand_guidelines)

        return self._create_default_plan(product)

    def _parse_creative_response(
        self, response: str, product: Any, brand_guidelines: str
    ) -> CreativePlan:
        """解析创意响应。

        Args:
            response: LLM响应。
            product: 商品信息。
            brand_guidelines: 品牌规范。

        Returns:
            创意方案。
        """
        data = extract_json(response)
        if data is not None:
            style_str = data.get("visual_style", "modern").upper()
            try:
                visual_style = VisualStyle[style_str]
            except KeyError:
                visual_style = VisualStyle.MODERN

            color_name = data.get("color_suggestion", "tech")
            palette = self._get_palette(color_name, brand_guidelines)

            return CreativePlan(
                name=data.get("theme_name", "默认创意主题"),
                description=data.get("theme_description", ""),
                visual_style=visual_style,
                style_keywords=data.get("style_keywords", []),
                color_palette=palette,
                key_elements=data.get("key_elements", []),
                target_emotion=data.get("target_emotion"),
            )

        return self._create_default_plan(product)

    def _get_palette(self, name: str, _brand_guidelines: str = "") -> ColorPalette:
        """获取配色方案。

        Args:
            name: 方案名称。
            _brand_guidelines: 品牌规范。

        Returns:
            配色方案。
        """
        # 这里可以解析品牌规范中的色彩定义
        # 简化处理：使用预设方案
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
        category = (
            product.category.value if hasattr(product.category, "value") else str(product.category)
        )
        palette_name = "tech"
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
