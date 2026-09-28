"""
CrossEncoderReranker 行为级测试。

Description:
    只通过公开 rerank 接口验证打分排序、top_k 截断、
    开关关闭与异常降级路径，不测内部私有函数。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.reranker import CrossEncoderReranker, get_reranker


def _create_search_result(
    chunk_id: int,
    content: str,
    similarity: float,
) -> SearchResult:
    """创建 SearchResult 辅助函数。

    Args:
        chunk_id: 分块 ID。
        content: 分块内容。
        similarity: 原始相似度。

    Returns:
        SearchResult 实例。
    """
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=chunk_id,
        content=content,
        similarity=similarity,
        metadata={"source": "test"},
        doc_title=f"文档{chunk_id}",
        doc_type="brand_guide",
    )


def _fake_flag_embedding(compute_score: Any) -> MagicMock:
    """构造假 FlagEmbedding 模块，返回可控打分。

    Args:
        compute_score: 模型 compute_score 的返回值（标量或列表）。

    Returns:
        可注入 sys.modules 的假模块。
    """
    fake_module = MagicMock()
    fake_model = MagicMock()
    fake_model.compute_score = MagicMock(return_value=compute_score)
    fake_module.FlagReranker = MagicMock(return_value=fake_model)
    return fake_module


class TestRerankOrdering:
    """重排序顺序、截断与元数据行为。"""

    @pytest.fixture
    def reranker(self) -> CrossEncoderReranker:
        """创建启用重排序的实例。"""
        settings = MagicMock()
        settings.reranker_enabled = True
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 5
        settings.reranker_device = "cpu"
        with patch("src.rag.reranker.get_settings", return_value=settings):
            return CrossEncoderReranker()

    @pytest.mark.asyncio
    async def test_rerank_orders_by_model_score_desc(self, reranker: CrossEncoderReranker) -> None:
        """模型分数决定最终顺序，与原始相似度无关。"""
        results = [
            _create_search_result(1, "低分内容", 0.9),
            _create_search_result(2, "高分内容", 0.1),
            _create_search_result(3, "中分内容", 0.5),
        ]
        fake = _fake_flag_embedding([0.2, 0.95, 0.6])

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results)

        assert [r.chunk_id for r in result.results] == [2, 3, 1]
        assert result.original_count == 3
        assert result.reranked_count == 3

    @pytest.mark.asyncio
    async def test_rerank_preserves_original_similarity_in_metadata(
        self, reranker: CrossEncoderReranker
    ) -> None:
        """重排序分数写入 similarity，原始相似度存入 metadata。"""
        results = [_create_search_result(1, "内容", 0.42)]
        fake = _fake_flag_embedding([0.8])

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results)

        assert result.results[0].similarity == 0.8
        assert result.results[0].metadata["original_similarity"] == 0.42
        assert result.results[0].metadata["source"] == "test"

    @pytest.mark.asyncio
    async def test_rerank_truncates_to_explicit_top_k(self, reranker: CrossEncoderReranker) -> None:
        """显式 top_k 优先于配置值。"""
        results = [_create_search_result(i, f"内容{i}", 0.5) for i in range(1, 5)]
        fake = _fake_flag_embedding([0.1, 0.9, 0.3, 0.7])

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results, top_k=2)

        assert result.reranked_count == 2
        assert [r.chunk_id for r in result.results] == [2, 4]

    @pytest.mark.asyncio
    async def test_rerank_truncates_to_settings_top_k_when_omitted(
        self, reranker: CrossEncoderReranker
    ) -> None:
        """未传 top_k 时使用配置的 reranker_top_k。"""
        reranker.settings.reranker_top_k = 1
        results = [_create_search_result(i, f"内容{i}", 0.5) for i in range(1, 4)]
        fake = _fake_flag_embedding([0.1, 0.2, 0.9])

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results)

        assert result.reranked_count == 1
        assert result.results[0].chunk_id == 3

    @pytest.mark.asyncio
    async def test_rerank_accepts_scalar_score_from_model(
        self, reranker: CrossEncoderReranker
    ) -> None:
        """模型对单文档返回标量分数时同样可用。"""
        results = [_create_search_result(1, "内容", 0.5)]
        fake = _fake_flag_embedding(0.77)

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results)

        assert result.results[0].similarity == 0.77


class TestRerankDegradation:
    """开关关闭与异常降级路径。"""

    @pytest.fixture
    def enabled_reranker(self) -> CrossEncoderReranker:
        """创建启用重排序的实例。"""
        settings = MagicMock()
        settings.reranker_enabled = True
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 3
        settings.reranker_device = "cpu"
        with patch("src.rag.reranker.get_settings", return_value=settings):
            return CrossEncoderReranker()

    @pytest.mark.asyncio
    async def test_disabled_switch_returns_results_unchanged(
        self,
    ) -> None:
        """reranker_enabled=False 时原样返回，不触碰模型。"""
        settings = MagicMock()
        settings.reranker_enabled = False
        with patch("src.rag.reranker.get_settings", return_value=settings):
            reranker = CrossEncoderReranker()

        results = [_create_search_result(1, "内容", 0.5)]
        fake = _fake_flag_embedding([0.9])

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await reranker.rerank("查询", results)

        assert result.results == results
        assert result.results[0].similarity == 0.5
        fake.FlagReranker.assert_not_called()

    @pytest.mark.asyncio
    async def test_model_failure_falls_back_to_original_order(
        self, enabled_reranker: CrossEncoderReranker
    ) -> None:
        """打分异常时按原始顺序截断返回。"""
        results = [
            _create_search_result(1, "内容1", 0.9),
            _create_search_result(2, "内容2", 0.8),
            _create_search_result(3, "内容3", 0.7),
            _create_search_result(4, "内容4", 0.6),
        ]
        fake = _fake_flag_embedding([0.1])
        fake.FlagReranker.return_value.compute_score = MagicMock(
            side_effect=RuntimeError("模型不可用")
        )

        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            result = await enabled_reranker.rerank("查询", results, top_k=2)

        assert [r.chunk_id for r in result.results] == [1, 2]
        assert result.original_count == 4
        assert result.reranked_count == 2

    @pytest.mark.asyncio
    async def test_missing_flagembedding_falls_back_to_original_order(
        self, enabled_reranker: CrossEncoderReranker
    ) -> None:
        """FlagEmbedding 未安装时降级为返回原始结果。"""
        results = [_create_search_result(1, "内容1", 0.9)]

        with patch.dict("sys.modules", {"FlagEmbedding": None}):
            result = await enabled_reranker.rerank("查询", results, top_k=5)

        assert result.results == results
        assert result.reranked_count == 1


class TestRerankerDeviceResolution:
    """模型设备选择行为（auto/cuda/cpu）。"""

    @pytest.mark.asyncio
    async def test_explicit_device_is_passed_through(self) -> None:
        """device=cpu 时模型按 cpu 加载。"""
        settings = MagicMock()
        settings.reranker_enabled = True
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 5
        settings.reranker_device = "cpu"
        with patch("src.rag.reranker.get_settings", return_value=settings):
            reranker = CrossEncoderReranker()

        fake = _fake_flag_embedding([0.5])
        with patch.dict("sys.modules", {"FlagEmbedding": fake}):
            await reranker.rerank("查询", [_create_search_result(1, "内容", 0.5)])

        assert fake.FlagReranker.call_args.kwargs["device"] == "cpu"

    @pytest.mark.asyncio
    async def test_auto_device_prefers_cuda_when_available(self) -> None:
        """device=auto 且 CUDA 可用时加载到 cuda。"""
        settings = MagicMock()
        settings.reranker_enabled = True
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 5
        settings.reranker_device = "auto"
        with patch("src.rag.reranker.get_settings", return_value=settings):
            reranker = CrossEncoderReranker()

        fake = _fake_flag_embedding([0.5])
        fake_torch = MagicMock()
        fake_torch.cuda.is_available = MagicMock(return_value=True)
        with patch.dict("sys.modules", {"FlagEmbedding": fake, "torch": fake_torch}):
            await reranker.rerank("查询", [_create_search_result(1, "内容", 0.5)])

        assert fake.FlagReranker.call_args.kwargs["device"] == "cuda"

    @pytest.mark.asyncio
    async def test_auto_device_falls_back_to_cpu_without_torch(self) -> None:
        """device=auto 且无 torch 时回退 cpu。"""
        settings = MagicMock()
        settings.reranker_enabled = True
        settings.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.reranker_top_k = 5
        settings.reranker_device = "auto"
        with patch("src.rag.reranker.get_settings", return_value=settings):
            reranker = CrossEncoderReranker()

        fake = _fake_flag_embedding([0.5])
        with patch.dict("sys.modules", {"FlagEmbedding": fake, "torch": None}):
            await reranker.rerank("查询", [_create_search_result(1, "内容", 0.5)])

        assert fake.FlagReranker.call_args.kwargs["device"] == "cpu"


class TestGetReranker:
    """get_reranker 单例行为。"""

    def test_returns_singleton(self) -> None:
        """重复调用返回同一实例。"""
        import src.rag.reranker as reranker_module

        original = reranker_module._reranker
        try:
            reranker_module._reranker = None
            first = get_reranker()
            second = get_reranker()
            assert first is second
        finally:
            reranker_module._reranker = original
