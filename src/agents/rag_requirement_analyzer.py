"""
RAG增强的需求分析Agent模块。

Description:
    基于知识库检索的需求分析Agent，通过RAG增强商品分析和卖点提炼。
    主要功能：
    - 知识库检索增强的商品分析
    - 基于历史案例的卖点提炼
    - 类目知识辅助的风格推荐
    - 合规关键词过滤
@author ganjianfei
@version 1.0.0
2026-04-05
"""

import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.graph.state import RequirementReport


class RAGEnhancedRequirementAnalyzer(BaseAgent[AgentState]):
    """RAG增强的需求分析Agent。

    通过知识库检索增强商品分析能力：
    - 品牌文档：获取品牌调性和视觉规范
    - 类目知识：获取类目特征和热门卖点
    - 历史案例：参考成功案例的卖点提炼
    - 合规规则：避免违规词汇

    Example:
        >>> from src.rag.retriever import KnowledgeRetriever
        >>> retriever = KnowledgeRetriever()
        >>> agent = RAGEnhancedRequirementAnalyzer(retriever=retriever)
        >>> result = await agent.execute(state, session)
    """

    def __init__(self, session: AsyncSession | None = None, **kwargs: Any) -> None:
        """初始化RAG增强需求分析Agent。

        Args:
            session: 数据库会话，用于知识检索。
            **kwargs: 传递给父类的参数。
        """
        super().__init__(role=AgentRole.REQUIREMENT_ANALYZER, **kwargs)
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
        # RAG增强的商品分析提示
        analysis_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个电商商品分析专家。"
                    "请结合提供的知识库信息，深入分析商品信息。\n\n"
                    "【知识库参考信息】\n{knowledge_context}\n\n"
                    "请输出JSON格式的分析报告，包含以下字段：\n"
                    "- product_summary: 商品一句话摘要（20字以内）\n"
                    "- key_features: 关键特性列表（3-5个）\n"
                    "- selling_points: 卖点列表，每个包含title、description、priority\n"
                    "- target_audience: 目标人群标签\n"
                    "- style_recommendations: 推荐的视觉风格\n"
                    "- keywords: SEO关键词\n\n"
                    "注意：\n"
                    "1. 参考知识库中的品牌调性和视觉规范\n"
                    "2. 借鉴历史成功案例的卖点提炼方式\n"
                    "3. 避免使用知识库中标记的违规词汇",
                ),
                (
                    "human",
                    "商品名称：{name}\n"
                    "品牌：{brand}\n"
                    "类目：{category}\n"
                    "描述：{description}\n"
                    "规格：{specifications}\n"
                    "已有卖点：{existing_selling_points}\n\n"
                    "请结合知识库信息分析商品并输出结构化报告。",
                ),
            ]
        )
        self.register_prompt("rag_analysis", analysis_prompt)

        # 卖点提炼提示
        selling_point_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个营销文案专家。"
                    "请根据商品描述和知识库参考信息，提炼最具吸引力的卖点。\n\n"
                    "【类目成功案例参考】\n{category_cases}\n\n"
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
        self.register_prompt("rag_selling_point", selling_point_prompt)

    async def execute(self, state: AgentState) -> AgentResult:
        """执行RAG增强的需求分析。

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

            # RAG检索相关知识
            knowledge_context = await self._retrieve_knowledge(state)

            # 执行分析
            report = await self._analyze_product_with_rag(product, knowledge_context)

            # 更新状态
            state.requirement_report = report
            state.selling_points = report.selling_points
            state.rag_context = knowledge_context
            state.mark_step_completed("requirement_analysis")

            return AgentResult(
                success=True,
                data={
                    "requirement_report": report.model_dump(),
                    "selling_points": report.selling_points,
                    "rag_context_used": bool(knowledge_context),
                },
                next_agent=AgentRole.CREATIVE_PLANNER,
            )

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"需求分析失败: {e}",
            )

    async def _retrieve_knowledge(self, state: AgentState) -> str:
        """检索相关知识。

        Args:
            state: 当前状态。

        Returns:
            检索到的知识上下文。
        """
        if not self.has_rag() or not self._session:
            return ""

        product = state.product_info
        if not product:
            return ""

        from src.rag.retriever import KnowledgeRetriever

        if not isinstance(self._retriever, KnowledgeRetriever):
            return ""

        context_parts: list[str] = []

        # 检索品牌文档
        if product.brand:
            brand_results = await self._retriever.retrieve(
                self._session,
                query=f"{product.brand} 品牌调性 视觉规范",
                doc_type="brand_guide",
                top_k=3,
            )
            if brand_results.results:
                context_parts.append(
                    "【品牌规范】\n"
                    + "\n".join([r.content[:500] for r in brand_results.results[:2]])
                )

        # 检索类目知识
        category = (
            product.category.value if hasattr(product.category, "value") else str(product.category)
        )
        category_results = await self._retriever.retrieve(
            self._session,
            query=f"{category} 商品特点 卖点关键词",
            doc_type="category_knowledge",
            top_k=3,
        )
        if category_results.results:
            context_parts.append(
                "【类目知识】\n"
                + "\n".join([r.content[:500] for r in category_results.results[:2]])
            )

        # 检索成功案例
        case_results = await self._retriever.retrieve(
            self._session,
            query=f"{category} {product.name[:20]} 成功案例",
            doc_type="case_study",
            top_k=2,
        )
        if case_results.results:
            context_parts.append(
                "【成功案例参考】\n"
                + "\n".join([r.content[:300] for r in case_results.results[:2]])
            )

        # 记录RAG来源
        state.rag_sources = [
            {
                "query": r.query,
                "chunk_id": r.chunk_id,
                "doc_id": r.doc_id,
                "similarity": r.similarity,
            }
            for r in (brand_results.results + category_results.results + case_results.results)
        ]

        return "\n\n".join(context_parts) if context_parts else ""

    async def _analyze_product_with_rag(
        self,
        product: Any,
        knowledge_context: str,
    ) -> RequirementReport:
        """使用RAG知识分析商品。

        Args:
            product: 商品信息。
            knowledge_context: 知识库上下文。

        Returns:
            需求分析报告。
        """
        existing_points = [
            {"title": sp.title, "description": sp.description} for sp in product.selling_points
        ]

        prompt = self.get_prompt("rag_analysis")
        if prompt is None:
            return self._create_default_report(product)

        response = await self.invoke_llm(
            prompt,
            {
                "knowledge_context": knowledge_context or "暂无相关知识库内容",
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

        return self._parse_analysis_response(response, product)

    def _parse_analysis_response(
        self,
        response: str,
        product: Any,
    ) -> RequirementReport:
        """解析分析响应。

        Args:
            response: LLM响应。
            product: 商品信息。

        Returns:
            需求分析报告。
        """
        try:
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
