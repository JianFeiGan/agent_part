"""
需求分析Agent模块。

Description:
    负责深入分析商品信息，提取核心卖点和风格特征。
    主要功能：
    - 解析商品属性
    - 提取核心卖点
    - 分析目标人群
    - 推荐视觉风格
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.graph.state import RequirementReport


class RequirementAnalyzerAgent(BaseAgent[AgentState]):
    """需求分析Agent。

    深入分析商品信息，生成结构化的需求分析报告。

    Example:
        >>> agent = RequirementAnalyzerAgent()
        >>> result = await agent.execute(state)
        >>> report = result.data.get("requirement_report")
    """

    def __init__(self, **kwargs: Any) -> None:
        """初始化需求分析Agent。"""
        super().__init__(role=AgentRole.REQUIREMENT_ANALYZER, **kwargs)
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """设置提示模板。"""
        # 商品分析提示
        analysis_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个电商商品分析专家。"
                    "请深入分析以下商品信息，提取关键信息。\n\n"
                    "请输出JSON格式的分析报告，包含以下字段：\n"
                    "- product_summary: 商品一句话摘要（20字以内）\n"
                    "- key_features: 关键特性列表（3-5个）\n"
                    "- selling_points: 卖点列表，每个包含title、description、priority\n"
                    "- target_audience: 目标人群标签\n"
                    "- style_recommendations: 推荐的视觉风格\n"
                    "- keywords: SEO关键词",
                ),
                (
                    "human",
                    "商品名称：{name}\n"
                    "品牌：{brand}\n"
                    "类目：{category}\n"
                    "描述：{description}\n"
                    "规格：{specifications}\n"
                    "已有卖点：{existing_selling_points}\n\n"
                    "请分析商品并输出结构化报告。",
                ),
            ]
        )
        self.register_prompt("analysis", analysis_prompt)

        # 卖点提炼提示
        selling_point_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个营销文案专家。"
                    "请根据商品描述提炼出最具吸引力的卖点。\n\n"
                    "卖点分类：\n"
                    "- 功能卖点：产品功能优势\n"
                    "- 情感卖点：情感价值诉求\n"
                    "- 差异化卖点：与竞品的区别\n"
                    "- 场景卖点：使用场景描述",
                ),
                (
                    "human",
                    "商品：{product_name}\n"
                    "描述：{description}\n"
                    "类目：{category}\n\n"
                    "请提炼5个核心卖点，输出JSON数组。",
                ),
            ]
        )
        self.register_prompt("selling_point", selling_point_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行需求分析。

        Args:
            state: 当前状态。

        Returns:
            包含需求分析报告的结果。
        """
        try:
            product = state.product_info
            if product is None:
                return AgentResult(
                    success=False,
                    error="缺少商品信息",
                )

            # 执行分析
            report = await self._analyze_product(product)

            # 更新状态
            state.requirement_report = report
            state.selling_points = report.selling_points
            state.mark_step_completed("requirement_analysis")

            return AgentResult(
                success=True,
                data={
                    "requirement_report": report.model_dump(),
                    "selling_points": report.selling_points,
                },
                next_agent=AgentRole.CREATIVE_PLANNER,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"需求分析失败: {e}",
            )

    async def _analyze_product(self, product: Any) -> RequirementReport:
        """分析商品信息。

        Args:
            product: 商品信息。

        Returns:
            需求分析报告。
        """
        # 准备输入
        existing_points = [
            {"title": sp.title, "description": sp.description} for sp in product.selling_points
        ]

        prompt = self.get_prompt("analysis")
        if prompt is None:
            return self._create_default_report(product)

        response = await self.invoke_llm(
            prompt,
            {
                "name": product.name,
                "brand": product.brand or "未知品牌",
                "category": product.category.value
                if hasattr(product.category, "value")
                else str(product.category),
                "description": product.description,
                "specifications": str(product.specifications) if product.specifications else "无",
                "existing_selling_points": str(existing_points) if existing_points else "无",
            },
        )

        # 解析响应
        return self._parse_analysis_response(response, product)

    def _parse_analysis_response(self, response: str, product: Any) -> RequirementReport:
        """解析分析响应。

        Args:
            response: LLM响应。
            product: 商品信息。

        Returns:
            需求分析报告。
        """
        try:
            # 提取JSON
            start = response.find("{")
            end = response.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(response[start:end])
                return RequirementReport(
                    product_summary=data.get("product_summary", product.name),
                    key_features=data.get("key_features", []),
                    selling_points=data.get("selling_points", []),
                    target_audience=data.get("target_audience", []),
                    style_recommendations=data.get("style_recommendations", []),
                    keywords=data.get("keywords", []),
                )
        except json.JSONDecodeError:
            pass

        return self._create_default_report(product)

    def _create_default_report(self, product: Any) -> RequirementReport:
        """创建默认报告。

        Args:
            product: 商品信息。

        Returns:
            默认的需求分析报告。
        """
        return RequirementReport(
            product_summary=product.name,
            key_features=["高品质", "实用性强", "性价比高"],
            selling_points=[
                {
                    "title": "品质保证",
                    "description": "严格品质控制，确保产品可靠性",
                    "priority": 5,
                }
            ],
            target_audience=["消费者"],
            style_recommendations=["简约现代", "专业大气"],
            keywords=[product.name],
        )
