"""记忆链路补充行为测试。

覆盖 MemoryStore 的分类降级、向量化失败降级、检索过滤与遗忘管理，
以及 MemoryClassifier 的 LLM 主路径与不可识别结果回退。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.rag.memory_classifier import MemoryClassifier, MemoryType
from src.rag.memory_store import MemoryStore, get_memory_store

# --------------------------------------------------------------------------- #
# 夹具
# --------------------------------------------------------------------------- #


def _session(memories: list[Any] | None = None) -> AsyncMock:
    """构造返回固定记忆列表的会话。"""
    session = AsyncMock()
    result = MagicMock()
    scalars = MagicMock()
    scalars.all = MagicMock(return_value=memories or [])
    result.scalars = MagicMock(return_value=scalars)
    result.scalar = MagicMock(return_value=0)
    result.all = MagicMock(return_value=[])
    result.rowcount = 0
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _memory(**kwargs: Any) -> MagicMock:
    """构造 AgentMemory 风格对象。"""
    memory = MagicMock()
    memory.access_count = kwargs.get("access_count", 0)
    memory.last_accessed_at = None
    memory.id = kwargs.get("id", 1)
    return memory


def _store(**settings: Any) -> MemoryStore:
    """构造注入可控 settings 的 MemoryStore。"""
    defaults: dict[str, Any] = {
        "memory_auto_classify": True,
        "memory_max_per_type": 3,
        "memory_forget_threshold_days": 30,
    }
    defaults.update(settings)
    store = MemoryStore()
    store.settings = SimpleNamespace(**defaults)
    return store


def _patch_embedding(monkeypatch: pytest.MonkeyPatch, vector: Any) -> MagicMock:
    """注入假 embedding 服务。"""
    service = MagicMock()
    service.aembed_single = AsyncMock(return_value=vector)
    monkeypatch.setattr("src.rag.memory_store.get_embedding_service", lambda: service)
    return service


class TestStoreClassification:
    """store 的分类决策。"""

    async def test_auto_classify_disabled_falls_back_to_semantic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """关闭自动分类时默认语义记忆。"""
        store = _store(memory_auto_classify=False)
        store._classifier.classify = AsyncMock()  # noqa: SLF001
        store._classifier.extract_key_concepts = AsyncMock(return_value=[])  # noqa: SLF001
        _patch_embedding(monkeypatch, [0.1])
        session = _session()

        memory = await store.store(session, content="知识", agent_name="A")

        store._classifier.classify.assert_not_awaited()  # noqa: SLF001
        assert memory.memory_type == MemoryType.SEMANTIC.value

    async def test_explicit_type_skips_classifier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """显式指定类型时不再自动分类。"""
        store = _store()
        store._classifier.classify = AsyncMock()  # noqa: SLF001
        store._classifier.extract_key_concepts = AsyncMock(return_value=[])  # noqa: SLF001
        _patch_embedding(monkeypatch, [0.1])
        session = _session()

        memory = await store.store(
            session, content="c", agent_name="A", memory_type=MemoryType.PROCEDURAL
        )

        store._classifier.classify.assert_not_awaited()  # noqa: SLF001
        assert memory.memory_type == MemoryType.PROCEDURAL.value

    async def test_embedding_failure_still_stores(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """向量化失败只告警，记忆仍入库（无向量）。"""
        store = _store()
        store._classifier.classify = AsyncMock(return_value=MemoryType.SEMANTIC)  # noqa: SLF001
        store._classifier.extract_key_concepts = AsyncMock(return_value=[])  # noqa: SLF001
        service = MagicMock()
        service.aembed_single = AsyncMock(side_effect=RuntimeError("emb down"))
        monkeypatch.setattr("src.rag.memory_store.get_embedding_service", lambda: service)
        session = _session()

        memory = await store.store(session, content="c", agent_name="A")

        assert memory.embedding is None
        session.add.assert_called_once()


class TestRetrieve:
    """retrieve 的过滤与排序。"""

    async def test_query_embedding_failure_falls_back_to_importance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """查询向量化失败时按重要性排序。"""
        store = _store()
        service = MagicMock()
        service.aembed_single = AsyncMock(side_effect=RuntimeError("emb down"))
        monkeypatch.setattr("src.rag.memory_store.get_embedding_service", lambda: service)
        session = _session([_memory(), _memory(id=2)])

        memories = await store.retrieve(session, "query", "A")

        assert len(memories) == 2
        session.flush.assert_awaited_once()

    async def test_filters_by_type_and_category(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """类型与类目过滤条件生效（不抛异常即视为查询构造成功）。"""
        store = _store()
        _patch_embedding(monkeypatch, [0.5])
        session = _session([_memory()])

        memories = await store.retrieve(
            session,
            "q",
            "A",
            memory_type=MemoryType.EPISODIC,
            category="digital",
            top_k=2,
            tenant_id="tenant-1",
        )

        assert len(memories) == 1

    async def test_increments_access_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """命中记忆的访问计数 +1 并刷新时间戳。"""
        store = _store()
        _patch_embedding(monkeypatch, [0.5])
        memory = _memory(access_count=4)
        session = _session([memory])

        await store.retrieve(session, "q", "A")

        assert memory.access_count == 5
        assert memory.last_accessed_at is not None

    async def test_without_tenant_uses_null_filter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未传 tenant_id 时限定 tenant_id 为空的记录。"""
        store = _store()
        _patch_embedding(monkeypatch, None)
        session = _session([])

        assert await store.retrieve(session, "q", "A") == []


class TestForget:
    """遗忘管理。"""

    async def test_capacity_overflow_forgets_least_important(self) -> None:
        """超出上限时删除低重要性记忆。"""
        store = _store(memory_max_per_type=2)
        session = _session()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=5)
        ids_result = MagicMock()
        ids_result.all = MagicMock(return_value=[(10,), (11,)])
        delete_result = MagicMock()
        session.execute = AsyncMock(side_effect=[count_result, ids_result, delete_result])

        await store._check_capacity(  # noqa: SLF001
            session, "A", MemoryType.SEMANTIC, tenant_id="t1"
        )

        # 计数 -> 查低分 id -> 删除
        assert session.execute.await_count == 3
        session.flush.assert_awaited_once()

    async def test_within_capacity_does_not_forget(self) -> None:
        """未超限时不触发遗忘。"""
        store = _store(memory_max_per_type=10)
        session = _session()
        count_result = MagicMock()
        count_result.scalar = MagicMock(return_value=2)
        session.execute = AsyncMock(return_value=count_result)

        await store._check_capacity(session, "A", MemoryType.SEMANTIC)  # noqa: SLF001

        assert session.execute.await_count == 1

    async def test_forget_expired_returns_rowcount(self) -> None:
        """清理过期记忆返回删除数量。"""
        store = _store()
        session = _session()
        result = MagicMock()
        result.rowcount = 3
        session.execute = AsyncMock(return_value=result)

        assert await store.forget_expired(session, tenant_id="t1") == 3

    async def test_forget_least_important_with_no_rows(self) -> None:
        """无候选时返回 0 且不执行 delete。"""
        store = _store()
        session = _session()
        result = MagicMock()
        result.all = MagicMock(return_value=[])
        session.execute = AsyncMock(return_value=result)

        deleted = await store._forget_least_important(  # noqa: SLF001
            session, "A", MemoryType.SEMANTIC, count=2
        )

        assert deleted == 0
        assert session.execute.await_count == 1


class TestSingleton:
    """get_memory_store 单例。"""

    def test_returns_same_instance(self) -> None:
        """重复调用返回同一实例。"""
        first = get_memory_store()
        assert get_memory_store() is first


class TestClassifierLLMPaths:
    """MemoryClassifier 的 LLM 主路径。"""

    def _classifier_with_llm(self, llm: Any) -> MemoryClassifier:
        classifier = MemoryClassifier()
        classifier.settings = SimpleNamespace(
            llm_provider="qwen",
            effective_dashscope_api_key="",
            llm_model="m",
        )
        classifier._llm = llm  # noqa: SLF001
        return classifier

    async def test_classify_uses_llm_result(self) -> None:
        """LLM 返回可识别类型时采用其结果。"""

        class _LLM:
            async def ainvoke(self, _prompt: str) -> Any:
                return SimpleNamespace(content="procedural")

        classifier = self._classifier_with_llm(_LLM())

        assert await classifier.classify("步骤：先做A") is MemoryType.PROCEDURAL

    async def test_classify_unrecognized_falls_back_to_rules(self) -> None:
        """LLM 结果不可识别时回退规则分类。"""

        class _LLM:
            async def ainvoke(self, _prompt: str) -> Any:
                return SimpleNamespace(content="not-a-type")

        classifier = self._classifier_with_llm(_LLM())

        result = await classifier.classify("这是一个定义类的事实")

        assert result is MemoryType.SEMANTIC

    async def test_classify_llm_error_falls_back_to_rules(self) -> None:
        """LLM 调用失败回退规则分类。"""

        class _Boom:
            async def ainvoke(self, _prompt: str) -> Any:
                raise RuntimeError("llm down")

        classifier = self._classifier_with_llm(_Boom())

        assert await classifier.classify("步骤：先做A") is MemoryType.PROCEDURAL

    async def test_extract_key_concepts_parses_json_array(self) -> None:
        """从 LLM 输出中解析 JSON 数组概念。"""

        class _LLM:
            async def ainvoke(self, _prompt: str) -> Any:
                return SimpleNamespace(content='["概念A", "概念B"]')

        classifier = self._classifier_with_llm(_LLM())

        assert await classifier.extract_key_concepts("文本") == ["概念A", "概念B"]

    async def test_extract_key_concepts_handles_non_json(self) -> None:
        """LLM 未返回 JSON 数组时返回空列表。"""

        class _LLM:
            async def ainvoke(self, _prompt: str) -> Any:
                return SimpleNamespace(content="没有数组")

        classifier = self._classifier_with_llm(_LLM())

        assert await classifier.extract_key_concepts("文本") == []

    async def test_extract_key_concepts_error_returns_empty(self) -> None:
        """提取失败返回空列表，不向上抛。"""

        class _Boom:
            async def ainvoke(self, _prompt: str) -> Any:
                raise RuntimeError("llm down")

        classifier = self._classifier_with_llm(_Boom())

        assert await classifier.extract_key_concepts("文本") == []

    def test_rule_based_breaks_tie_by_declaration_order(self) -> None:
        """规则分类同分时按声明顺序取首个。"""
        classifier = MemoryClassifier()
        result = classifier._rule_based_classify(  # noqa: SLF001
            "定义与步骤与经历同时出现"
        )
        assert result in set(MemoryType)
