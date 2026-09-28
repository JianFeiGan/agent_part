"""Embedding 服务行为测试。

覆盖 qwen / 本地两条提供商路径的同步与异步入口、维度查询、
以及本地模型未安装时的显式 ImportError。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rag.embeddings import EmbeddingService

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _service(**kwargs: Any) -> EmbeddingService:
    """构造注入假 settings 的 EmbeddingService。"""
    defaults: dict[str, Any] = {
        "embedding_provider": "local",
        "embedding_model": "bge-large-zh",
        "embedding_device": "cpu",
        "qwen_embedding_dimensions": 8,
    }
    defaults.update(kwargs)
    service = EmbeddingService()
    service.settings = SimpleNamespace(**defaults)
    return service


def _with_model(service: EmbeddingService, vectors: Any) -> MagicMock:
    """注入假本地模型。"""
    model = MagicMock()
    model.encode = MagicMock(return_value=vectors)
    model.get_sentence_embedding_dimension = MagicMock(return_value=768)
    service._model = model  # noqa: SLF001
    service._initialized = True  # noqa: SLF001
    return model


class _Vec(list[float]):
    """带 tolist() 的向量替身（模拟 numpy 数组）。"""

    def tolist(self) -> list[float]:
        return list(self)


class TestQwenProviderPaths:
    """embedding_provider=qwen 路径。"""

    async def test_aembed_single_delegates_to_client(self) -> None:
        """异步单条向量化走千问客户端。"""
        service = _service(embedding_provider="qwen")
        client = MagicMock()
        client.embed = AsyncMock(return_value=[0.5])
        service._qwen_client = client  # noqa: SLF001

        assert await service.aembed_single("hi") == [0.5]
        client.embed.assert_awaited_once_with("hi")

    async def test_aembed_batch_delegates_to_client(self) -> None:
        """异步批量向量化走千问客户端。"""
        service = _service(embedding_provider="qwen")
        client = MagicMock()
        client.embed_batch = AsyncMock(return_value=[[1.0], [2.0]])
        service._qwen_client = client  # noqa: SLF001

        assert await service.aembed_batch(["a", "b"]) == [[1.0], [2.0]]
        client.embed_batch.assert_awaited_once_with(["a", "b"])

    def test_dimension_from_settings(self) -> None:
        """千问维度取 Settings 配置。"""
        assert _service(embedding_provider="qwen").dimension == 8

    def test_sync_embed_raises_for_qwen(self) -> None:
        """千问不支持同步调用，显式引导改用异步。"""
        service = _service(embedding_provider="qwen")
        with pytest.raises(RuntimeError, match="aembed_single"):
            service.embed_single("hi")

    def test_sync_embed_batch_raises_for_qwen(self) -> None:
        """千问批量同步同样显式失败。"""
        service = _service(embedding_provider="qwen")
        with pytest.raises(RuntimeError, match="aembed_batch"):
            service.embed_batch(["hi"])

    async def test_qwen_client_is_created_lazily(self) -> None:
        """首次调用时才构造千问客户端并缓存。"""
        service = _service(embedding_provider="qwen")
        fake_cls = MagicMock()
        fake_instance = MagicMock()
        fake_instance.embed = AsyncMock(return_value=[1.0])
        fake_cls.return_value = fake_instance

        import src.clients.qwen_embedding_client as qwen_mod

        original = qwen_mod.QwenEmbeddingClient
        qwen_mod.QwenEmbeddingClient = fake_cls  # type: ignore[misc]
        try:
            assert await service.aembed_single("x") == [1.0]
            assert await service.aembed_single("y") == [1.0]
        finally:
            qwen_mod.QwenEmbeddingClient = original  # type: ignore[misc]

        fake_cls.assert_called_once()


class TestLocalProviderPaths:
    """embedding_provider=local 路径。"""

    def test_embed_single_uses_model(self) -> None:
        """同步单条向量化调用本地模型。"""
        service = _service()
        model = _with_model(service, _Vec([0.1, 0.2]))

        assert service.embed_single("hi") == [0.1, 0.2]
        model.encode.assert_called_once()

    def test_embed_batch_uses_model(self) -> None:
        """同步批量向量化返回列表的列表。"""
        service = _service()
        _with_model(service, [_Vec([1.0]), _Vec([2.0])])

        assert service.embed_batch(["a", "b"]) == [[1.0], [2.0]]

    def test_embed_batch_shows_progress_for_large_batch(self) -> None:
        """超过 100 条时开启进度条。"""
        service = _service()
        model = _with_model(service, [_Vec([0.0])] * 101)

        service.embed_batch([f"t{i}" for i in range(101)])

        assert model.encode.call_args.kwargs["show_progress_bar"] is True

    def test_dimension_from_model(self) -> None:
        """本地维度取模型输出。"""
        service = _service()
        _with_model(service, None)

        assert service.dimension == 768

    async def test_aembed_single_wraps_sync_in_thread(self) -> None:
        """本地异步入口在线程中跑同步实现。"""
        service = _service()
        _with_model(service, _Vec([0.3]))

        assert await service.aembed_single("hi") == [0.3]

    async def test_aembed_batch_wraps_sync_in_thread(self) -> None:
        """本地批量异步入口同样在线程中执行。"""
        service = _service()
        _with_model(service, [_Vec([0.1]), _Vec([0.2])])

        assert await service.aembed_batch(["a", "b"]) == [[0.1], [0.2]]

    def test_missing_sentence_transformers_raises_import_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """本地模型依赖缺失时抛 ImportError 并提示安装。"""
        import builtins

        real_import = builtins.__import__

        def _blocked(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "sentence_transformers":
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _blocked)
        service = _service()

        with pytest.raises(ImportError, match="sentence-transformers"):
            service._ensure_model_loaded()  # noqa: SLF001

    def test_model_loaded_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """重复调用只加载一次模型。"""
        service = _service()
        fake_cls = MagicMock()
        fake_cls.return_value = MagicMock(
            get_sentence_embedding_dimension=MagicMock(return_value=4)
        )

        # 绕过 from-import，直接在 _ensure_model_loaded 内的 import 处注入
        monkeypatch.setitem(
            __import__("sys").modules,
            "sentence_transformers",
            MagicMock(SentenceTransformer=fake_cls),
        )
        service._ensure_model_loaded()  # noqa: SLF001
        service._ensure_model_loaded()  # noqa: SLF001

        fake_cls.assert_called_once()
