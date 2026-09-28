"""
HybridRetriever 行为级测试。

Description:
    只通过公开 search/encode 接口验证三路检索融合顺序、权重与 RRF 常数的作用，
    以及开关关闭与异常降级路径。
@author ganjianfei
@version 1.0.0
2026-09-28
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_store import SearchResult
from src.rag.hybrid_retriever import HybridRetriever, get_hybrid_retriever


def _create_search_result(
    chunk_id: int,
    content: str,
    similarity: float,
) -> SearchResult:
    """创建 SearchResult 辅助函数。

    Args:
        chunk_id: 分块 ID。
        content: 分块内容。
        similarity: 相似度。

    Returns:
        SearchResult 实例。
    """
    return SearchResult(
        chunk_id=chunk_id,
        doc_id=chunk_id,
        content=content,
        similarity=similarity,
        metadata={},
        doc_title=f"文档{chunk_id}",
        doc_type="brand_guide",
    )


def _sparse_row(
    chunk_id: int,
    content: str,
    similarity: float | None,
) -> MagicMock:
    """构造 Sparse SQL 查询返回的行对象。

    Args:
        chunk_id: 分块 ID。
        content: 分块内容。
        similarity: ts_rank 分数，None 模拟空值。

    Returns:
        行对象。
    """
    row = MagicMock()
    row.chunk_id = chunk_id
    row.doc_id = chunk_id
    row.content = content
    row.metadata = {"channel": "sparse"}
    row.doc_title = f"文档{chunk_id}"
    row.doc_type = "brand_guide"
    row.similarity = similarity
    return row


def _make_settings(**overrides: Any) -> MagicMock:
    """构造混合检索配置。

    Args:
        **overrides: 覆盖的配置项。

    Returns:
        配置 Mock。
    """
    settings = MagicMock()
    settings.hybrid_retrieval_enabled = True
    settings.hybrid_model = "BAAI/bge-m3"
    settings.hybrid_dense_weight = 0.4
    settings.hybrid_sparse_weight = 0.3
    settings.hybrid_colbert_weight = 0.3
    settings.hybrid_rrf_k = 60
    settings.retrieval_top_k = 5
    settings.embedding_device = "cpu"
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


class _FakeSession:
    """只实现 execute 的假会话，用于 Sparse 全文检索。"""

    def __init__(self, rows: list[MagicMock], fail: bool = False) -> None:
        """初始化假会话。

        Args:
            rows: Sparse 查询返回的行。
            fail: 是否让 execute 抛异常。
        """
        self._rows = rows
        self._fail = fail
        self.calls: list[Any] = []

    async def execute(self, stmt: Any, params: Any = None) -> MagicMock:
        """返回预置行，或按需抛异常。

        Args:
            stmt: SQL 语句。
            params: 查询参数。

        Returns:
            带 fetchall 的结果对象。
        """
        self.calls.append((stmt, params))
        if self._fail:
            raise RuntimeError("全文检索不可用")
        result = MagicMock()
        result.fetchall = MagicMock(return_value=self._rows)
        return result


def _build_retriever(settings: MagicMock) -> HybridRetriever:
    """构造带 Mock 依赖的 HybridRetriever。

    Args:
        settings: 配置 Mock。

    Returns:
        HybridRetriever 实例。
    """
    with (
        patch("src.rag.hybrid_retriever.get_settings", return_value=settings),
        patch("src.rag.hybrid_retriever.get_embedding_service"),
        patch("src.rag.hybrid_retriever.VectorStore"),
    ):
        return HybridRetriever()


def _wire_backends(
    retriever: HybridRetriever,
    dense_results: list[SearchResult],
) -> None:
    """注入 embedding 与向量检索后端。

    Args:
        retriever: 检索器实例。
        dense_results: Dense 检索返回的结果。
    """
    mock_embedding = MagicMock()
    mock_embedding.aembed_single = AsyncMock(return_value=[0.1, 0.2])
    retriever.embedding_service = mock_embedding

    mock_vs = MagicMock()
    mock_vs.search = AsyncMock(return_value=dense_results)
    retriever.vector_store = mock_vs


class TestHybridSearchFusion:
    """混合检索融合顺序与计数。"""

    @pytest.mark.asyncio
    async def test_search_fuses_dense_and_sparse_by_rrf(self) -> None:
        """多路命中的文档在融合结果中排名更高。"""
        retriever = _build_retriever(_make_settings())
        dense = [
            _create_search_result(1, "dense-1", 0.9),
            _create_search_result(2, "dense-2", 0.8),
        ]
        _wire_backends(retriever, dense)
        session = _FakeSession(
            [
                _sparse_row(2, "sparse-2", 0.7),
                _sparse_row(3, "sparse-3", 0.6),
            ]
        )

        result = await retriever.search(session, "查询", tenant_id="t1")

        assert result.method == "hybrid"
        assert result.dense_count == 2
        assert result.sparse_count == 2
        # ColBERT 复用 Dense 结果
        assert result.colbert_count == 2
        # 文档 2 同时命中 Dense + Sparse + ColBERT，应排第一
        assert result.results[0].chunk_id == 2
        assert {r.chunk_id for r in result.results} == {1, 2, 3}
        # 融合分数写入 similarity 与 metadata
        for item in result.results:
            assert item.similarity == item.metadata["rrf_score"]

    @pytest.mark.asyncio
    async def test_sparse_only_chunk_enters_results_with_metadata(self) -> None:
        """仅命中 Sparse 的文档保留其元数据并进入融合结果。"""
        retriever = _build_retriever(_make_settings())
        _wire_backends(retriever, [_create_search_result(1, "dense-1", 0.9)])
        session = _FakeSession([_sparse_row(9, "仅稀疏命中", 0.4)])

        result = await retriever.search(session, "查询", tenant_id="t1")

        sparse_only = next(r for r in result.results if r.chunk_id == 9)
        assert sparse_only.content == "仅稀疏命中"
        assert sparse_only.metadata["channel"] == "sparse"
        assert sparse_only.doc_title == "文档9"

    @pytest.mark.asyncio
    async def test_sparse_row_without_similarity_scores_zero(self) -> None:
        """Sparse 行 similarity 为空时记 0.0。"""
        retriever = _build_retriever(_make_settings())
        _wire_backends(retriever, [_create_search_result(1, "dense-1", 0.9)])
        session = _FakeSession([_sparse_row(9, "无分数", None)])

        result = await retriever.search(session, "查询", tenant_id="t1")

        target = next(r for r in result.results if r.chunk_id == 9)
        # 融合后 similarity 被 RRF 分数覆盖，原始字段映射体现在进入结果集
        assert target.metadata["rrf_score"] > 0


class TestRrfWeightsAndConstant:
    """权重与 RRF 融合常数对融合顺序/分数的影响。"""

    @pytest.mark.asyncio
    async def test_sparse_weight_can_outrank_dense_only_hit(self) -> None:
        """提高 Sparse 权重可让仅 Sparse 命中的文档反超。"""
        dense = [_create_search_result(1, "dense-1", 0.9)]
        sparse_rows = [_sparse_row(2, "sparse-2", 0.7)]
        session_factory = lambda: _FakeSession(sparse_rows)  # noqa: E731

        # 默认权重：Dense 0.4 > Sparse 0.3，文档 1 靠前
        baseline = _build_retriever(_make_settings())
        _wire_backends(baseline, dense)
        baseline_result = await baseline.search(session_factory(), "查询", tenant_id="t1")
        assert baseline_result.results[0].chunk_id == 1

        # Sparse 权重调高后顺序反转
        boosted = _build_retriever(
            _make_settings(hybrid_sparse_weight=5.0, hybrid_dense_weight=0.01)
        )
        _wire_backends(boosted, dense)
        boosted_result = await boosted.search(session_factory(), "查询", tenant_id="t1")
        assert boosted_result.results[0].chunk_id == 2

    @pytest.mark.asyncio
    async def test_rrf_k_constant_changes_fused_scores(self) -> None:
        """RRF 常数 k 越小，靠前名次的分数越高。"""
        dense = [_create_search_result(1, "dense-1", 0.9)]
        sparse_rows = [_sparse_row(2, "sparse-2", 0.7)]

        small_k = _build_retriever(_make_settings(hybrid_rrf_k=1))
        _wire_backends(small_k, dense)
        small_result = await small_k.search(_FakeSession(sparse_rows), "q", tenant_id="t1")

        large_k = _build_retriever(_make_settings(hybrid_rrf_k=1000))
        _wire_backends(large_k, dense)
        large_result = await large_k.search(_FakeSession(sparse_rows), "q", tenant_id="t1")

        small_score = small_result.results[0].metadata["rrf_score"]
        large_score = large_result.results[0].metadata["rrf_score"]
        assert small_score > large_score

    @pytest.mark.asyncio
    async def test_colbert_weight_affects_fusion_score(self) -> None:
        """ColBERT 路（复用 Dense）权重计入融合分数。"""
        dense = [_create_search_result(1, "dense-1", 0.9)]

        base = _build_retriever(_make_settings(hybrid_colbert_weight=0.0))
        _wire_backends(base, dense)
        base_result = await base.search(_FakeSession([]), "q", tenant_id="t1")

        boosted = _build_retriever(_make_settings(hybrid_colbert_weight=10.0))
        _wire_backends(boosted, dense)
        boosted_result = await boosted.search(_FakeSession([]), "q", tenant_id="t1")

        assert (
            boosted_result.results[0].metadata["rrf_score"]
            > base_result.results[0].metadata["rrf_score"]
        )


class TestHybridSearchSwitches:
    """开关关闭与降级路径。"""

    @pytest.mark.asyncio
    async def test_disabled_switch_uses_pure_dense(self) -> None:
        """hybrid_retrieval_enabled=False 时只走 Dense。"""
        retriever = _build_retriever(_make_settings(hybrid_retrieval_enabled=False))
        dense = [_create_search_result(1, "dense-1", 0.85)]
        _wire_backends(retriever, dense)
        session = _FakeSession([_sparse_row(2, "不应出现", 0.9)])

        result = await retriever.search(session, "查询", tenant_id="t1")

        assert result.method == "dense"
        assert [r.chunk_id for r in result.results] == [1]
        assert result.sparse_count == 0
        assert session.calls == []

    @pytest.mark.asyncio
    async def test_sparse_failure_falls_back_to_dense(self) -> None:
        """混合检索内部失败时回退 Dense，标记 dense_fallback。"""
        retriever = _build_retriever(_make_settings())
        dense = [_create_search_result(1, "dense-1", 0.85)]
        _wire_backends(retriever, dense)
        session = _FakeSession([], fail=True)

        result = await retriever.search(session, "查询", tenant_id="t1", top_k=3)

        assert result.method == "dense_fallback"
        assert [r.chunk_id for r in result.results] == [1]
        assert result.dense_count == 1

    @pytest.mark.asyncio
    async def test_top_k_defaults_to_settings_and_truncates_fusion(self) -> None:
        """未传 top_k 时用 retrieval_top_k 截断融合结果。"""
        retriever = _build_retriever(_make_settings(retrieval_top_k=2))
        dense = [_create_search_result(i, f"dense-{i}", 0.9 - i * 0.05) for i in range(1, 6)]
        _wire_backends(retriever, dense)
        session = _FakeSession([])

        result = await retriever.search(session, "查询", tenant_id="t1")

        assert len(result.results) == 2
        # Dense 侧按 top_k*3 多取用于融合
        assert retriever.vector_store.search.await_args.kwargs["top_k"] == 6


class TestHybridEncode:
    """BGE-M3 三路编码行为。"""

    def test_encode_returns_three_way_representation(self) -> None:
        """encode 返回 dense/sparse/colbert 三路表示。"""
        retriever = _build_retriever(_make_settings())

        fake_module = MagicMock()
        fake_model = MagicMock()
        fake_model.encode = MagicMock(
            return_value={
                "dense_vecs": [[0.1, 0.2]],
                "lexical_weights": [{"a": 1.0}],
                "colbert_vecs": [[[0.1, 0.2]]],
            }
        )
        fake_module.BGEM3FlagModel = MagicMock(return_value=fake_model)

        with patch.dict("sys.modules", {"FlagEmbedding": fake_module}):
            encoding = retriever.encode(["智能手表"])

        assert encoding["dense_embedding"] == [[0.1, 0.2]]
        assert encoding["sparse_weights"] == [{"a": 1.0}]
        assert encoding["colbert_vecs"] == [[[0.1, 0.2]]]
        assert fake_model.encode.call_args.kwargs["return_dense"] is True
        assert fake_model.encode.call_args.kwargs["return_sparse"] is True
        assert fake_model.encode.call_args.kwargs["return_colbert_vecs"] is True

    def test_encode_raises_without_flagembedding(self) -> None:
        """FlagEmbedding 未安装时 encode 明确失败。"""
        retriever = _build_retriever(_make_settings())

        with (
            patch.dict("sys.modules", {"FlagEmbedding": None}),
            pytest.raises(ImportError, match="FlagEmbedding"),
        ):
            retriever.encode(["查询"])

    def test_encode_resolves_auto_device_to_cpu_without_torch(self) -> None:
        """device=auto 且无 torch 时模型加载到 cpu。"""
        retriever = _build_retriever(_make_settings(embedding_device="auto"))

        fake_module = MagicMock()
        fake_model = MagicMock()
        fake_model.encode = MagicMock(return_value={})
        fake_module.BGEM3FlagModel = MagicMock(return_value=fake_model)

        with patch.dict("sys.modules", {"FlagEmbedding": fake_module, "torch": None}):
            retriever.encode(["查询"])

        assert fake_module.BGEM3FlagModel.call_args.kwargs["device"] == "cpu"

    def test_encode_resolves_auto_device_to_cuda_when_available(self) -> None:
        """device=auto 且 CUDA 可用时模型加载到 cuda。"""
        retriever = _build_retriever(_make_settings(embedding_device="auto"))

        fake_module = MagicMock()
        fake_model = MagicMock()
        fake_model.encode = MagicMock(return_value={})
        fake_module.BGEM3FlagModel = MagicMock(return_value=fake_model)
        fake_torch = MagicMock()
        fake_torch.cuda.is_available = MagicMock(return_value=True)

        with patch.dict("sys.modules", {"FlagEmbedding": fake_module, "torch": fake_torch}):
            retriever.encode(["查询"])

        assert fake_module.BGEM3FlagModel.call_args.kwargs["device"] == "cuda"

    def test_encode_is_idempotent_after_model_load(self) -> None:
        """模型只加载一次，后续 encode 复用。"""
        retriever = _build_retriever(_make_settings())

        fake_module = MagicMock()
        fake_model = MagicMock()
        fake_model.encode = MagicMock(return_value={})
        fake_module.BGEM3FlagModel = MagicMock(return_value=fake_model)

        with patch.dict("sys.modules", {"FlagEmbedding": fake_module}):
            retriever.encode(["a"])
            retriever.encode(["b"])

        assert fake_module.BGEM3FlagModel.call_count == 1
        assert fake_model.encode.call_count == 2


class TestGetHybridRetriever:
    """get_hybrid_retriever 单例行为。"""

    def test_returns_singleton(self) -> None:
        """重复调用返回同一实例。"""
        import src.rag.hybrid_retriever as hybrid_module

        original = hybrid_module._hybrid_retriever
        try:
            hybrid_module._hybrid_retriever = None
            first = get_hybrid_retriever()
            second = get_hybrid_retriever()
            assert first is second
        finally:
            hybrid_module._hybrid_retriever = original
