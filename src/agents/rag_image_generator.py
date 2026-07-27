"""
RAG 增强图片生成 Agent。

Description:
    在图片生成前检索品牌视觉规范、风格模板和成功案例，
    将 RAG 上下文注入图片生成 Prompt，提升生成质量。
    生成结果自动入库知识库作为案例积累。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import AgentResult, AgentRole, AgentState, BaseAgent
from src.agents.image_generator import ImageGeneratorAgent
from src.rag.retriever import KnowledgeRetriever, RetrievalResult

logger = logging.getLogger(__name__)


class RAGEnhancedImageGenerator(BaseAgent[AgentState]):
    """RAG 增强图片生成 Agent。

    在 ImageGeneratorAgent 基础上增加：
    1. 生成前检索品牌视觉规范和风格模板
    2. 将 RAG 上下文注入 Prompt 优化
    3. 生成结果自动入库知识库

    Example:
        >>> agent = RAGEnhancedImageGenerator(retriever=retriever)
        >>> result = await agent.execute(state)
    """

    def __init__(
        self,
        base_agent: ImageGeneratorAgent | None = None,
        retriever: KnowledgeRetriever | None = None,
        session: AsyncSession | None = None,
        **kwargs: Any,
    ) -> None:
        """初始化 RAG 增强图片生成 Agent。

        Args:
            base_agent: 基础图片生成 Agent 实例。
            retriever: 知识检索器实例。
            session: 数据库会话，用于 RAG 检索。
            **kwargs: 传递给 BaseAgent 的参数。
        """
        super().__init__(role=AgentRole.IMAGE_GENERATOR, **kwargs)
        self.base_agent = base_agent or ImageGeneratorAgent()
        self._retriever = retriever
        self._session = session

    def set_session(self, session: AsyncSession) -> None:
        """设置数据库会话。

        Args:
            session: 数据库会话。
        """
        self._session = session

    async def execute(self, state: AgentState) -> AgentResult:
        """执行 RAG 增强的图片生成。

        在调用基础图片生成前，先检索品牌视觉规范和风格模板，
        将 RAG 上下文注入 generation_prompts 中的 prompt 字段。

        Args:
            state: 当前状态。

        Returns:
            包含生成图片的结果。
        """
        try:
            # Step 1: RAG 检索增强 Prompt
            rag_context = ""
            rag_sources: list[dict[str, Any]] = []

            if self._retriever and self._session and state.rag_enabled:
                rag_result = await self._retrieve_image_knowledge(state)
                rag_context = rag_result.context
                rag_sources = rag_result.sources

                # 增强 generation_prompts 中的 prompt
                if rag_context and state.generation_prompts:
                    enhanced_prompts = []
                    for prompt_data in state.generation_prompts:
                        original_prompt = prompt_data.get("prompt", "")
                        enhanced_prompt = self._build_enhanced_prompt(
                            original_prompt=original_prompt,
                            rag_context=rag_context,
                            _category=self._get_category(state),
                            brand=self._get_brand(state),
                            style_preference=self._get_style_preference(state),
                        )
                        enhanced_data = {**prompt_data, "prompt": enhanced_prompt}
                        enhanced_data["original_prompt"] = original_prompt
                        enhanced_prompts.append(enhanced_data)
                    state.generation_prompts = enhanced_prompts

                    logger.info(
                        f"RAG-enhanced {len(enhanced_prompts)} prompts, "
                        f"rag_sources={len(rag_sources)}"
                    )

            # Step 2: 调用基础图片生成 Agent
            result = await self.base_agent.execute(state)

            # Step 3: 附加 RAG 信息到结果
            if result.success and rag_sources:
                result.data["rag_sources"] = rag_sources
                result.data["rag_context_length"] = len(rag_context)
                result.data["image_rag_enhanced"] = True

            return result

        except Exception as e:
            return AgentResult(
                success=False,
                error=f"RAG 增强图片生成失败: {e}",
            )

    async def _retrieve_image_knowledge(self, state: AgentState) -> RetrievalResult:
        """检索图片生成相关知识。

        Args:
            state: 当前状态。

        Returns:
            检索结果。
        """
        if not self._retriever or not self._session:
            return RetrievalResult(
                query="图片生成: 无",
                results=[],
                context="",
                sources=[],
            )

        category = self._get_category(state)
        brand = self._get_brand(state)
        style_preference = self._get_style_preference(state)
        tenant_id = self._resolve_tenant_id(state)

        return await self._retriever.retrieve_for_image_generation(
            self._session,
            category=category,
            brand=brand,
            style_preference=style_preference,
            tenant_id=tenant_id,
        )

    def _build_enhanced_prompt(
        self,
        original_prompt: str,
        rag_context: str,
        _category: str,
        brand: str | None = None,
        style_preference: str | None = None,
    ) -> str:
        """构建 RAG 增强的图片生成 Prompt。

        Args:
            original_prompt: 原始 Prompt。
            rag_context: RAG 检索上下文。
            _category: 商品类目（预留扩展）。
            brand: 品牌名称。
            style_preference: 风格偏好。

        Returns:
            增强后的 Prompt。
        """
        if not rag_context:
            return original_prompt

        context_section = f"【品牌视觉规范参考】\n{rag_context}\n"

        enhanced_parts = [
            original_prompt,
            "\n\n请遵循以下视觉规范：",
            context_section,
        ]

        if brand:
            enhanced_parts.append(f"品牌：{brand}，请确保图片风格与品牌调性一致。")

        if style_preference:
            enhanced_parts.append(f"风格偏好：{style_preference}。")

        enhanced_parts.append("请基于以上规范生成图片，确保构图、配色、风格与参考规范一致。")

        return "\n".join(enhanced_parts)

    def _get_category(self, state: AgentState) -> str:
        """从状态中获取商品类目。

        Args:
            state: 当前状态。

        Returns:
            商品类目字符串。
        """
        if state.product_info and hasattr(state.product_info, "category"):
            cat = state.product_info.category
            return cat.value if hasattr(cat, "value") else str(cat)
        return "general"

    def _get_brand(self, state: AgentState) -> str | None:
        """从状态中获取品牌名称。

        Args:
            state: 当前状态。

        Returns:
            品牌名称。
        """
        if state.product_info and hasattr(state.product_info, "brand"):
            return state.product_info.brand
        return None

    def _get_style_preference(self, state: AgentState) -> str | None:
        """从状态中获取风格偏好。

        Args:
            state: 当前状态。

        Returns:
            风格偏好。
        """
        if state.generation_request and state.generation_request.style_preference:
            return state.generation_request.style_preference
        return None

    def _resolve_tenant_id(self, state: AgentState) -> str:
        """从状态中解析 tenant_id。

        Args:
            state: 当前状态。

        Returns:
            tenant_id 字符串。
        """
        if state.generation_request is not None:
            req_tenant = getattr(state.generation_request, "tenant_id", None)
            if req_tenant:
                return req_tenant
        if state.product_info is not None:
            prod_tenant = getattr(state.product_info, "tenant_id", None)
            if prod_tenant:
                return prod_tenant
        state_tenant = getattr(state, "tenant_id", None)
        if state_tenant:
            return state_tenant
        return "system"

    async def ingest_generation_result(
        self,
        session: AsyncSession,
        prompt: str,
        enhanced_prompt: str,
        image_url: str,
        category: str,
        brand: str | None = None,
        quality_score: float | None = None,
        *,
        tenant_id: str,
    ) -> int | None:
        """将图片生成结果入库知识库作为案例积累。

        高质量生成结果自动作为 case_study 入库。

        Args:
            session: 数据库会话。
            prompt: 原始 Prompt。
            enhanced_prompt: 增强后的 Prompt。
            image_url: 生成图片 URL。
            category: 商品类目。
            brand: 品牌名称。
            quality_score: 质量评分。
            tenant_id: 租户 ID。

        Returns:
            入库文档 ID，失败返回 None。
        """
        # 仅入库高质量结果（评分 >= 0.7 或无评分）
        if quality_score is not None and quality_score < 0.7:
            logger.info(f"Skipping ingestion: quality score {quality_score} < 0.7")
            return None

        try:
            from src.db.models import KnowledgeDoc
            from src.db.vector_store import VectorStore
            from src.rag.document_processor import DocumentProcessor
            from src.rag.embeddings import get_embedding_service

            # 构建案例内容
            content_parts = [
                f"商品类目：{category}",
                f"品牌：{brand or '未指定'}",
                f"原始 Prompt：{prompt}",
                f"优化 Prompt：{enhanced_prompt}",
                f"生成图片：{image_url}",
            ]
            if quality_score is not None:
                content_parts.append(f"质量评分：{quality_score:.2f}")

            content = "\n".join(content_parts)
            title = f"[案例] {category} - {brand or '通用'} 图片生成"

            # 入库
            doc = KnowledgeDoc(
                tenant_id=tenant_id,
                title=title,
                doc_type="case_study",
                category=category,
                content=content,
                extra_data={
                    "image_url": image_url,
                    "quality_score": quality_score,
                    "brand": brand,
                    "auto_ingested": True,
                },
            )
            session.add(doc)
            await session.flush()

            # 分块 + 向量化
            processor = DocumentProcessor()
            parsed = processor.parse_content(content, title=title)
            chunks = processor.process(parsed)

            embedding_service = get_embedding_service()
            vector_store = VectorStore()

            embeddings = await embedding_service.aembed_batch([c["content"] for c in chunks])

            await vector_store.add_vectors(
                session,
                doc_id=doc.id,
                chunks=chunks,
                embeddings=embeddings,
                tenant_id=tenant_id,
            )

            logger.info(f"Ingested generation result as case_study: doc_id={doc.id}")
            return doc.id

        except Exception as e:
            logger.warning(f"Failed to ingest generation result: {e}")
            return None
