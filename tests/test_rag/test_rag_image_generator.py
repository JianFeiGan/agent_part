"""
RAG 增强图片生成 Agent 测试。

Description:
    测试 RAGEnhancedImageGenerator 的核心功能：
    - Prompt 增强构建
    - RAG 增强图片生成完整流程
    - 生成结果入库（高质量/低质量）
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.base import AgentResult
from src.agents.rag_image_generator import RAGEnhancedImageGenerator
from src.graph.state import AgentState, GenerationRequest
from src.rag.retriever import RetrievalResult


def _make_rag_result(context: str, sources: list[dict] | None = None) -> RetrievalResult:
    """构造 RetrievalResult 辅助函数。"""
    return RetrievalResult(
        query="图片生成: digital",
        results=[],
        context=context,
        sources=sources or [],
    )


def _make_state(
    prompts: list[dict] | None = None,
    rag_enabled: bool = True,
    brand: str | None = None,
    category: str = "digital",
    style_preference: str | None = None,
) -> AgentState:
    """构造 AgentState 辅助函数。"""
    state = AgentState(
        rag_enabled=rag_enabled,
        generation_prompts=prompts
        or [
            {"prompt": "智能手表主图", "image_type": "main"},
        ],
    )
    if brand or category:
        mock_product = MagicMock()
        mock_product.brand = brand
        mock_product.category = MagicMock()
        mock_product.category.value = category
        state.product_info = mock_product
    if style_preference:
        state.generation_request = GenerationRequest(style_preference=style_preference)
    return state


class TestBuildEnhancedPrompt:
    """_build_enhanced_prompt 方法测试类。"""

    def test_with_context(self) -> None:
        """测试 RAG 上下文注入 Prompt。"""
        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        result = agent._build_enhanced_prompt(
            original_prompt="智能手表主图",
            rag_context="品牌主色: #0066CC, 构图: 居中对称",
            _category="digital",
            brand="BrandX",
            style_preference="科技风",
        )

        assert "智能手表主图" in result
        assert "品牌视觉规范参考" in result
        assert "#0066CC" in result
        assert "BrandX" in result
        assert "科技风" in result
        assert "构图、配色、风格与参考规范一致" in result

    def test_without_context(self) -> None:
        """测试无 RAG 上下文时返回原始 Prompt。"""
        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        result = agent._build_enhanced_prompt(
            original_prompt="智能手表主图",
            rag_context="",
            _category="digital",
        )

        assert result == "智能手表主图"


class TestGenerateWithRAG:
    """execute 方法测试类。"""

    @pytest.mark.asyncio
    async def test_rag_enhanced_flow(self) -> None:
        """测试 RAG 增强图片生成完整流程。"""
        # Mock retriever
        mock_retriever = MagicMock()
        rag_result = _make_rag_result(
            context="品牌配色: 蓝色系",
            sources=[
                {
                    "chunk_id": 1,
                    "doc_id": 10,
                    "doc_title": "品牌规范",
                    "doc_type": "brand_guide",
                    "similarity": 0.9,
                }
            ],
        )
        mock_retriever.retrieve_for_image_generation = AsyncMock(return_value=rag_result)

        # Mock base_agent
        mock_base_agent = MagicMock()
        mock_base_agent.execute = AsyncMock(
            return_value=AgentResult(
                success=True,
                data={"generated_images": [{"url": "http://example.com/img.png"}]},
            )
        )

        mock_session = MagicMock()

        # 使用 __new__ 避免 BaseAgent.__init__ 的 LLM 初始化
        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        agent.base_agent = mock_base_agent
        agent._retriever = mock_retriever
        agent._session = mock_session

        state = _make_state(brand="BrandX", category="digital")

        result = await agent.execute(state)

        # 验证 retriever 被调用
        mock_retriever.retrieve_for_image_generation.assert_called_once()

        # 验证 base_agent.execute 被调用
        mock_base_agent.execute.assert_called_once()

        # 验证 RAG 信息附加到结果
        assert result.success is True
        assert result.data.get("rag_sources") == rag_result.sources
        assert result.data.get("image_rag_enhanced") is True

    @pytest.mark.asyncio
    async def test_no_rag_fallback(self) -> None:
        """测试无 RAG 配置时直接调用基础 Agent。"""
        mock_base_agent = MagicMock()
        mock_base_agent.execute = AsyncMock(
            return_value=AgentResult(
                success=True,
                data={"generated_images": []},
            )
        )

        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        agent.base_agent = mock_base_agent
        agent._retriever = None
        agent._session = None

        state = _make_state()

        result = await agent.execute(state)

        # 验证 base_agent.execute 被调用
        mock_base_agent.execute.assert_called_once()

        # 验证无 RAG 信息附加
        assert result.success is True
        assert "rag_sources" not in result.data


class TestIngestGenerationResult:
    """ingest_generation_result 方法测试类。"""

    @pytest.mark.asyncio
    async def test_ingest_high_quality_result(self) -> None:
        """测试高质量结果自动入库。"""
        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        mock_session = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.add = MagicMock()

        with (
            patch("src.db.models.KnowledgeDoc") as mock_doc_cls,
            patch("src.rag.document_processor.DocumentProcessor") as mock_processor_cls,
            patch("src.rag.embeddings.get_embedding_service") as mock_get_emb,
            patch("src.db.vector_store.VectorStore") as mock_vs_cls,
        ):
            # Mock KnowledgeDoc 实例
            mock_doc = MagicMock()
            mock_doc.id = 42
            mock_doc_cls.return_value = mock_doc

            # Mock DocumentProcessor
            mock_processor = MagicMock()
            mock_parsed = MagicMock()
            mock_processor.parse_content.return_value = mock_parsed
            mock_processor.process.return_value = [
                {"content": "测试分块内容", "metadata": {"title": "test"}},
            ]
            mock_processor_cls.return_value = mock_processor

            # Mock embedding service
            mock_emb_service = MagicMock()
            mock_emb_service.aembed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            mock_get_emb.return_value = mock_emb_service

            # Mock VectorStore
            mock_vs = MagicMock()
            mock_vs.add_vectors = AsyncMock(return_value=[])
            mock_vs_cls.return_value = mock_vs

            result = await agent.ingest_generation_result(
                mock_session,
                prompt="智能手表主图",
                enhanced_prompt="增强后Prompt",
                image_url="http://example.com/img.png",
                category="digital",
                brand="BrandX",
                quality_score=0.85,
                tenant_id="t1",
            )

            assert result == 42
            mock_doc_cls.assert_called_once()
            mock_vs.add_vectors.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_ingest_low_quality(self) -> None:
        """测试低质量结果不入库。"""
        agent = RAGEnhancedImageGenerator.__new__(RAGEnhancedImageGenerator)
        mock_session = MagicMock()

        result = await agent.ingest_generation_result(
            mock_session,
            prompt="智能手表主图",
            enhanced_prompt="增强后Prompt",
            image_url="http://example.com/img.png",
            category="digital",
            brand="BrandX",
            quality_score=0.5,
            tenant_id="t1",
        )

        assert result is None
