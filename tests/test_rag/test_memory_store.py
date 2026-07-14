"""
MemoryStore 测试。

Description:
    测试分类记忆存储服务的存储、检索、自动分类和遗忘管理功能。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.memory_classifier import MemoryType
from src.rag.memory_store import MemoryStore


class TestStoreAndRetrieve:
    """存储和检索测试类。"""

    @pytest.fixture
    def store(self) -> MemoryStore:
        """创建测试用存储实例。"""
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, store: MemoryStore) -> None:
        """测试记忆存储和检索。"""
        # Mock 分类器
        mock_classify_result = MemoryType.SEMANTIC
        with (
            patch.object(store._classifier, "classify", return_value=mock_classify_result),
            patch.object(
                store._classifier, "extract_key_concepts", return_value=["智能手表", "科技感"]
            ),
            patch("src.rag.memory_store.get_embedding_service") as mock_emb,
            patch.object(store, "_check_capacity", return_value=None),
        ):
            mock_emb_service = MagicMock()
            mock_emb_service.aembed_single = AsyncMock(return_value=[0.1] * 1024)
            mock_emb.return_value = mock_emb_service

            # Mock 数据库会话
            mock_session = AsyncMock()
            mock_memory = MagicMock()
            mock_memory.id = 1
            mock_memory.agent_name = "CreativePlanner"
            mock_memory.memory_type = "semantic"
            mock_memory.content = "智能手表需要突出科技感"
            mock_memory.key_concepts = ["智能手表", "科技感"]
            mock_memory.importance = 0.5

            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()

            await store.store(
                mock_session,
                content="智能手表需要突出科技感",
                agent_name="CreativePlanner",
            )

            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_retrieve(self, store: MemoryStore) -> None:
        """测试记忆检索。"""
        # Mock embedding 服务
        mock_memory = MagicMock()
        mock_memory.id = 1
        mock_memory.agent_name = "CreativePlanner"
        mock_memory.memory_type = "semantic"
        mock_memory.content = "智能手表需要突出科技感"
        mock_memory.access_count = 0
        mock_memory.last_accessed_at = None

        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[mock_memory])

        mock_result = MagicMock()
        mock_result.scalars = MagicMock(return_value=mock_scalars)

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        with patch("src.rag.memory_store.get_embedding_service") as mock_emb:
            mock_emb_service = MagicMock()
            mock_emb_service.aembed_single = AsyncMock(return_value=[0.1] * 1024)
            mock_emb.return_value = mock_emb_service

            results = await store.retrieve(
                mock_session,
                query="手表设计要点",
                agent_name="CreativePlanner",
            )

        assert len(results) == 1
        # 验证访问计数更新
        assert mock_memory.access_count == 1
        assert mock_memory.last_accessed_at is not None


class TestAutoClassify:
    """自动分类测试类。"""

    @pytest.fixture
    def store(self) -> MemoryStore:
        """创建测试用存储实例。"""
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_auto_classify(self, store: MemoryStore) -> None:
        """测试自动分类记忆。"""
        with (
            patch.object(store._classifier, "classify", return_value=MemoryType.EPISODIC),
            patch.object(store._classifier, "extract_key_concepts", return_value=["配色问题"]),
            patch("src.rag.memory_store.get_embedding_service") as mock_emb,
            patch.object(store, "_check_capacity", return_value=None),
        ):
            mock_emb_service = MagicMock()
            mock_emb_service.aembed_single = AsyncMock(return_value=[0.1] * 1024)
            mock_emb.return_value = mock_emb_service

            mock_session = AsyncMock()
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()

            await store.store(
                mock_session,
                content="上次遇到了配色问题",
                agent_name="CreativePlanner",
            )

            # 验证 add 被调用，且 memory_type 为 episodic
            added_obj = mock_session.add.call_args[0][0]
            assert added_obj.memory_type == "episodic"


class TestForgetExpired:
    """过期遗忘测试类。"""

    @pytest.fixture
    def store(self) -> MemoryStore:
        """创建测试用存储实例。"""
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_forget_expired(self, store: MemoryStore) -> None:
        """测试清理过期记忆。"""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.flush = AsyncMock()

        deleted = await store.forget_expired(mock_session)

        assert deleted == 3
        mock_session.execute.assert_called_once()


class TestForgetLeastImportant:
    """低重要性遗忘测试类。"""

    @pytest.fixture
    def store(self) -> MemoryStore:
        """创建测试用存储实例。"""
        return MemoryStore()

    @pytest.mark.asyncio
    async def test_forget_least_important(self, store: MemoryStore) -> None:
        """测试遗忘低重要性记忆。"""
        # Mock 查询最低评分记忆
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[(1,), (2,)])

        mock_query_result = MagicMock()
        mock_query_result.all = MagicMock(return_value=[(1,), (2,)])

        # Mock 删除操作
        mock_delete_result = MagicMock()

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_query_result, mock_delete_result])
        mock_session.flush = AsyncMock()

        deleted = await store._forget_least_important(
            mock_session,
            agent_name="CreativePlanner",
            memory_type=MemoryType.SEMANTIC,
            count=2,
        )

        assert deleted == 2
