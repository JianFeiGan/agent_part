"""
记忆分类器。

Description:
    使用 LLM 对记忆内容进行自动分类（情景记忆/语义记忆/程序记忆），
    LLM 不可用时回退到基于关键词的规则分类。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import json
import logging
import re
from enum import StrEnum
from typing import Any

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class MemoryType(StrEnum):
    """记忆类型枚举。

    Attributes:
        EPISODIC: 情景记忆 - 具体事件和经历。
        SEMANTIC: 语义记忆 - 事实和概念知识。
        PROCEDURAL: 程序记忆 - 操作步骤和方法。
    """

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


# 规则分类关键词映射
_EPISODIC_KEYWORDS = [
    "经历",
    "事件",
    "发生",
    "之前",
    "上次",
    "曾经",
    "历史",
    "过去",
    "遇到了",
    "处理了",
    "完成了",
    "失败了",
    "成功了",
]

_SEMANTIC_KEYWORDS = [
    "定义",
    "概念",
    "原理",
    "规则",
    "特点",
    "属性",
    "分类",
    "属于",
    "是指",
    "表示",
    "包含",
    "类型",
    "知识",
    "事实",
]

_PROCEDURAL_KEYWORDS = [
    "步骤",
    "方法",
    "流程",
    "操作",
    "如何",
    "怎样",
    "做法",
    "先",
    "然后",
    "接着",
    "最后",
    "需要",
    "应该",
    "必须",
]


class MemoryClassifier:
    """记忆分类器。

    使用 LLM 对记忆内容进行自动分类，LLM 不可用时回退到规则分类。

    Example:
        >>> classifier = MemoryClassifier()
        >>> memory_type = await classifier.classify("上次处理智能手表任务时遇到了配色问题")
        >>> print(memory_type)  # MemoryType.EPISODIC
    """

    def __init__(self) -> None:
        """初始化分类器。"""
        self.settings = get_settings()
        self._llm: Any = None

    async def _get_llm(self) -> Any:
        """懒加载 LLM 客户端。

        Returns:
            LLM 客户端实例。
        """
        if self._llm is None:
            settings = self.settings
            if settings.llm_provider == "qwen":
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
            elif settings.llm_provider == "dashscope" and settings.effective_dashscope_api_key:
                from langchain_community.chat_models import ChatTongyi

                self._llm = ChatTongyi(
                    model=settings.llm_model,
                    dashscope_api_key=settings.effective_dashscope_api_key,
                    temperature=0,
                )
            else:
                from src.clients.qwen_llm_client import get_qwen_llm

                self._llm = get_qwen_llm(settings=settings, temperature=0)
        return self._llm

    async def classify(self, content: str) -> MemoryType:
        """对记忆内容进行分类。

        优先使用 LLM 分类，失败时回退到规则分类。

        Args:
            content: 记忆内容文本。

        Returns:
            MemoryType 记忆类型。
        """
        try:
            llm = await self._get_llm()
            prompt = (
                f"请将以下记忆内容分类为三种类型之一：\n"
                f"- episodic（情景记忆）：具体事件、经历、历史记录\n"
                f"- semantic（语义记忆）：事实、概念、定义、知识\n"
                f"- procedural（程序记忆）：步骤、方法、流程、操作指南\n\n"
                f"记忆内容：{content}\n\n"
                f"只返回类型名称（episodic/semantic/procedural），不要包含其他内容。"
            )
            response = await llm.ainvoke(prompt)
            result = response.content.strip().lower()

            for mem_type in MemoryType:
                if mem_type.value in result:
                    return mem_type

            logger.warning(f"LLM 分类结果无法识别: {result}，回退到规则分类")
        except Exception as e:
            logger.warning(f"LLM 分类失败: {e}，回退到规则分类")

        return self._rule_based_classify(content)

    def _rule_based_classify(self, content: str) -> MemoryType:
        """基于关键词的规则分类回退。

        Args:
            content: 记忆内容文本。

        Returns:
            MemoryType 记忆类型。
        """
        scores: dict[MemoryType, int] = {
            MemoryType.EPISODIC: 0,
            MemoryType.SEMANTIC: 0,
            MemoryType.PROCEDURAL: 0,
        }

        for keyword in _EPISODIC_KEYWORDS:
            if keyword in content:
                scores[MemoryType.EPISODIC] += 1

        for keyword in _SEMANTIC_KEYWORDS:
            if keyword in content:
                scores[MemoryType.SEMANTIC] += 1

        for keyword in _PROCEDURAL_KEYWORDS:
            if keyword in content:
                scores[MemoryType.PROCEDURAL] += 1

        # 返回得分最高的类型，默认为语义记忆
        max_score = max(scores.values())
        if max_score == 0:
            return MemoryType.SEMANTIC

        for mem_type, score in scores.items():
            if score == max_score:
                return mem_type

        return MemoryType.SEMANTIC

    async def extract_key_concepts(self, content: str) -> list[str]:
        """使用 LLM 提取记忆内容的关键概念。

        Args:
            content: 记忆内容文本。

        Returns:
            关键概念列表。
        """
        try:
            llm = await self._get_llm()
            prompt = (
                f"请从以下记忆内容中提取关键概念（关键词或短语）。\n\n"
                f"记忆内容：{content}\n\n"
                f'请以 JSON 数组格式返回关键概念列表，例如：["概念1", "概念2"]\n'
                f"只返回 JSON 数组，不要包含其他内容。"
            )
            response = await llm.ainvoke(prompt)
            json_match = re.search(r"\[.*\]", response.content, re.DOTALL)
            if json_match:
                concepts = json.loads(json_match.group())
                if isinstance(concepts, list):
                    return [str(c).strip() for c in concepts if str(c).strip()]
        except Exception as e:
            logger.warning(f"关键概念提取失败: {e}")

        return []
