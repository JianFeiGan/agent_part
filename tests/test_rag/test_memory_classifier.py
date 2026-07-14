"""
MemoryClassifier 测试。

Description:
    测试记忆分类器的 LLM 分类和规则分类回退功能。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.memory_classifier import MemoryClassifier, MemoryType


class TestClassifyEpisodic:
    """情景记忆分类测试类。"""

    @pytest.fixture
    def classifier(self) -> MemoryClassifier:
        """创建测试用分类器实例。"""
        return MemoryClassifier()

    @pytest.mark.asyncio
    async def test_classify_episodic(self, classifier: MemoryClassifier) -> None:
        """测试 LLM 分类情景记忆。"""
        mock_response = MagicMock()
        mock_response.content = "episodic"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("上次处理智能手表任务时遇到了配色问题")

        assert result == MemoryType.EPISODIC


class TestClassifySemantic:
    """语义记忆分类测试类。"""

    @pytest.fixture
    def classifier(self) -> MemoryClassifier:
        """创建测试用分类器实例。"""
        return MemoryClassifier()

    @pytest.mark.asyncio
    async def test_classify_semantic(self, classifier: MemoryClassifier) -> None:
        """测试 LLM 分类语义记忆。"""
        mock_response = MagicMock()
        mock_response.content = "semantic"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("智能手表是指具有智能操作系统的可穿戴设备")

        assert result == MemoryType.SEMANTIC


class TestClassifyProcedural:
    """程序记忆分类测试类。"""

    @pytest.fixture
    def classifier(self) -> MemoryClassifier:
        """创建测试用分类器实例。"""
        return MemoryClassifier()

    @pytest.mark.asyncio
    async def test_classify_procedural(self, classifier: MemoryClassifier) -> None:
        """测试 LLM 分类程序记忆。"""
        mock_response = MagicMock()
        mock_response.content = "procedural"

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("生成商品图片时应该先分析卖点，然后选择风格")

        assert result == MemoryType.PROCEDURAL


class TestRuleBasedFallback:
    """规则分类回退测试类。"""

    @pytest.fixture
    def classifier(self) -> MemoryClassifier:
        """创建测试用分类器实例。"""
        return MemoryClassifier()

    @pytest.mark.asyncio
    async def test_rule_based_fallback_episodic(self, classifier: MemoryClassifier) -> None:
        """测试规则分类回退 - 情景记忆。"""
        # LLM 失败时回退到规则分类
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM 不可用"))

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("上次遇到了配色问题，处理失败了")

        assert result == MemoryType.EPISODIC

    @pytest.mark.asyncio
    async def test_rule_based_fallback_semantic(self, classifier: MemoryClassifier) -> None:
        """测试规则分类回退 - 语义记忆。"""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM 不可用"))

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("智能手表属于可穿戴设备类型")

        assert result == MemoryType.SEMANTIC

    @pytest.mark.asyncio
    async def test_rule_based_fallback_procedural(self, classifier: MemoryClassifier) -> None:
        """测试规则分类回退 - 程序记忆。"""
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM 不可用"))

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            result = await classifier.classify("生成图片的步骤：先分析需求，然后选择风格")

        assert result == MemoryType.PROCEDURAL

    def test_rule_based_no_keywords(self, classifier: MemoryClassifier) -> None:
        """测试无关键词时默认分类为语义记忆。"""
        result = classifier._rule_based_classify("这是一段普通文本")
        assert result == MemoryType.SEMANTIC
