"""存储层补充行为测试。

覆盖 AssetPersister 的构造校验与视频落库，
以及 VectorStore 的向量写入、按文档删除与统计聚合。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.service.asset_persister import AssetPersister
from src.db.vector_store import VectorStore
from src.models.assets import AssetStatus, GeneratedVideo

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _repo() -> MagicMock:
    """构造 AssetRepository 替身。"""
    repo = MagicMock()
    repo.create_asset = AsyncMock()
    return repo


def _video(**kwargs: Any) -> GeneratedVideo:
    """构造已完成视频。"""
    defaults: dict[str, Any] = {
        "video_id": "vid_001",
        "title": "产品短片",
        "visual_prompt": "video prompt",
        "url": "https://example.com/v.mp4",
        "duration": 8.0,
        "fps": 30,
        "width": 1920,
        "height": 1080,
        "status": AssetStatus.COMPLETED,
        "model": "kling-v1",
    }
    defaults.update(kwargs)
    return GeneratedVideo(**defaults)


def _session() -> AsyncMock:
    """构造覆盖 VectorStore 用法的会话。"""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.delete = AsyncMock()
    return session


class TestAssetPersisterInit:
    """构造校验。"""

    def test_requires_repo_or_session(self) -> None:
        """既无 repo 也无 session 时显式失败。"""
        with pytest.raises(ValueError, match="必须提供 repo 或 session"):
            AssetPersister()

    def test_builds_repo_from_session(self) -> None:
        """仅给 session 时自建 AssetRepository。"""
        persister = AssetPersister(session=AsyncMock())
        assert persister._repo is not None  # noqa: SLF001


class TestPersistVideos:
    """persist_videos。"""

    async def test_persists_ready_video(self) -> None:
        """就绪视频落库并返回 1。"""
        repo = _repo()
        persister = AssetPersister(repo=repo)

        count = await persister.persist_videos(
            tenant_id="tenant-1",
            product_id="prod_001",
            task_id="task_abc",
            video=_video(),
        )

        assert count == 1
        kwargs = repo.create_asset.call_args.kwargs
        assert kwargs["asset_type"] == "video"
        assert kwargs["duration"] == 8.0
        assert kwargs["is_mock"] is False
        assert kwargs["extra_data"]["video_id"] == "vid_001"

    async def test_skips_not_ready_video(self) -> None:
        """未就绪视频跳过落库，返回 0。"""
        repo = _repo()
        persister = AssetPersister(repo=repo)

        count = await persister.persist_videos(
            tenant_id="tenant-1",
            product_id="prod_001",
            task_id="task_abc",
            video=_video(status=AssetStatus.FAILED),
        )

        assert count == 0
        repo.create_asset.assert_not_called()

    async def test_marks_mock_video(self) -> None:
        """model=mock 的视频标记 is_mock。"""
        repo = _repo()
        persister = AssetPersister(repo=repo)

        await persister.persist_videos(
            tenant_id="tenant-1",
            product_id="prod_001",
            task_id="task_abc",
            video=_video(model="mock"),
        )

        assert repo.create_asset.call_args.kwargs["is_mock"] is True

    async def test_uses_local_path_when_no_url(self) -> None:
        """无 url 时以 local_path 兜底生成访问路径。"""
        repo = _repo()
        persister = AssetPersister(repo=repo)

        await persister.persist_videos(
            tenant_id="tenant-1",
            product_id="prod_001",
            task_id="task_abc",
            video=_video(url=None, local_path="output/v.mp4"),
        )

        kwargs = repo.create_asset.call_args.kwargs
        assert kwargs["url"] == "/output/output/v.mp4"
        assert kwargs["storage_key"] == "output/v.mp4"

    async def test_image_storage_key_prefers_local_path(self) -> None:
        """图片 storage_key 优先 local_path。"""
        from src.models.assets import GeneratedImage, ImageFormat

        repo = _repo()
        persister = AssetPersister(repo=repo)
        image = GeneratedImage(
            image_id="img",
            image_type="main",
            prompt="p",
            local_path="out/i.png",
            url="https://x/i.png",
            format=ImageFormat.PNG,
            status=AssetStatus.COMPLETED,
        )

        await persister.persist_images(
            tenant_id="t",
            product_id="p",
            task_id="task",
            images=[image],
        )

        assert repo.create_asset.call_args.kwargs["storage_key"] == "out/i.png"


class TestVectorStore:
    """VectorStore 写入 / 删除 / 统计。"""

    async def test_add_vectors_creates_chunk_rows(self) -> None:
        """按 chunk+embedding 建行并 flush。"""
        session = _session()
        store = VectorStore()
        chunks = [
            {"content": "c1", "metadata": {"k": 1}},
            {"content": "c2", "metadata": {}},
        ]
        embeddings = [[0.1], [0.2]]

        created = await store.add_vectors(
            session, doc_id=9, chunks=chunks, embeddings=embeddings, tenant_id="t1"
        )

        assert len(created) == 2
        assert session.add.call_count == 2
        session.flush.assert_awaited_once()
        assert created[0].chunk_index == 0
        assert created[1].content == "c2"

    async def test_add_vectors_rejects_length_mismatch(self) -> None:
        """chunks 与 embeddings 长度不一致时显式失败。"""
        store = VectorStore()
        with pytest.raises(ValueError):
            await store.add_vectors(
                _session(),
                doc_id=1,
                chunks=[{"content": "c"}],
                embeddings=[],
                tenant_id="t1",
            )

    async def test_delete_by_doc_id_returns_count(self) -> None:
        """删除返回被删分块数量。"""
        session = _session()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)
        store = VectorStore()

        assert await store.delete_by_doc_id(session, doc_id=3, tenant_id="t1") == 3
        assert session.delete.await_count == 3

    async def test_delete_by_doc_id_empty(self) -> None:
        """无分块时返回 0。"""
        session = _session()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all = MagicMock(return_value=[])
        result.scalars = MagicMock(return_value=scalars)
        session.execute = AsyncMock(return_value=result)
        store = VectorStore()

        assert await store.delete_by_doc_id(session, doc_id=3, tenant_id="t1") == 0
        session.delete.assert_not_called()

    async def test_get_stats_aggregates(self) -> None:
        """统计返回文档/分块数量与类型分布。"""
        session = _session()

        docs_result = MagicMock()
        docs_result.fetchall = MagicMock(return_value=[MagicMock(doc_type="guide", count=2)])
        chunks_result = MagicMock()
        chunks_result.scalar = MagicMock(return_value=7)
        total_docs_result = MagicMock()
        total_docs_result.scalar = MagicMock(return_value=5)
        session.execute = AsyncMock(side_effect=[docs_result, chunks_result, total_docs_result])

        stats = await VectorStore().get_stats(session, tenant_id="t1")

        assert stats == {
            "total_documents": 5,
            "total_chunks": 7,
            "documents_by_type": {"guide": 2},
        }
