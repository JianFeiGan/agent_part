"""
Query 改写服务。

Description:
    支持 Single/MultiQuery/HyDE 三种改写模式，提升 RAG 检索召回率。
    懒加载 LLM，改写失败时回退到原始查询。
@author ganjianfei
@version 1.0.0
2026-07-14
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


class RewrittenQuery(BaseModel):
    """改写后的查询。

    Attributes:
        query: 改写后的查询文本。
        mode: 改写模式。
        is_original: 是否为原始查询（未改写）。
    """

    query: str = Field(..., description="改写后的查询文本")
    mode: str = Field(..., description="改写模式: single/multi_query/hyde")
    is_original: bool = Field(default=False, description="是否为原始查询（未改写）")


@dataclass
class RewriteResult:
    """改写结果。

    Attributes:
        original_query: 原始查询。
        rewritten_queries: 改写后的查询列表。
        mode: 使用的改写模式。
    """

    original_query: str
    rewritten_queries: list[RewrittenQuery] = field(default_factory=list)
    mode: str = "single"

    @property
    def queries(self) -> list[str]:
        """获取所有查询文本。

        Returns:
            查询文本列表。
        """
        return [rq.query for rq in self.rewritten_queries]


class QueryRewriter:
    """Query 改写服务。

    支持三种改写模式：
    - single: LLM 单次改写，优化查询表达。
    - multi_query: 生成多个视角的查询变体。
    - hyde: 生成假设文档，用假设文档的语义进行检索。

    Example:
        >>> rewriter = QueryRewriter()
        >>> result = await rewriter.rewrite("智能手表特点")
        >>> print(result.queries)
    """

    def __init__(self) -> None:
        """初始化 Query 改写服务。"""
        self.settings = get_settings()
        self._llm: Any = None

    @property
    def llm(self) -> Any:
        """懒加载 LLM 实例。

        Returns:
            LangChain BaseChatModel 实例。
        """
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _create_llm(self) -> Any:
        """创建 LLM 实例。

        根据 llm_provider 配置选择 LLM。

        Returns:
            LangChain BaseChatModel 实例。

        Raises:
            ImportError: 缺少必要的依赖包。
            ValueError: 未配置 API Key。
        """
        provider = self.settings.llm_provider

        if provider == "qwen":
            from langchain_openai import ChatOpenAI

            api_key = self.settings.effective_qwen_api_key
            if not api_key:
                raise ValueError("QWEN_API_KEY 或 DASHSCOPE_API_KEY 未配置")

            return ChatOpenAI(
                model=self.settings.qwen_llm_model,
                api_key=api_key,
                base_url=self.settings.qwen_api_base,
                temperature=0.3,
            )

        # 默认使用 DashScope SDK
        from langchain_community.chat_models import ChatTongyi

        api_key = self.settings.effective_dashscope_api_key
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY 或 QWEN_API_KEY 未配置")

        return ChatTongyi(
            model=self.settings.llm_model,
            dashscope_api_key=api_key,
            temperature=0.3,
        )

    async def rewrite(self, query: str) -> RewriteResult:
        """执行 Query 改写。

        根据配置的改写模式执行改写，失败时回退到原始查询。

        Args:
            query: 原始查询文本。

        Returns:
            改写结果。
        """
        if not self.settings.query_rewriting_enabled:
            return RewriteResult(
                original_query=query,
                rewritten_queries=[RewrittenQuery(query=query, mode="none", is_original=True)],
                mode="none",
            )

        mode = self.settings.query_rewriting_mode

        try:
            if mode == "multi_query":
                return await self._multi_query_rewrite(query)
            elif mode == "hyde":
                return await self._hyde_rewrite(query)
            else:
                return await self._single_rewrite(query)
        except Exception as e:
            logger.warning(f"Query 改写失败，回退到原始查询: {e}")
            return RewriteResult(
                original_query=query,
                rewritten_queries=[RewrittenQuery(query=query, mode=mode, is_original=True)],
                mode=mode,
            )

    async def _single_rewrite(self, query: str) -> RewriteResult:
        """单次改写模式。

        使用 LLM 优化查询表达，使其更适合检索。

        Args:
            query: 原始查询。

        Returns:
            改写结果。
        """
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个查询优化专家。请将用户的查询改写为更适合语义检索的形式。"
                    "保持查询的核心意图，但使用更精确、更具体的表达。"
                    "只输出改写后的查询，不要添加任何解释。",
                ),
                ("human", "原始查询: {query}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke({"query": query})
        rewritten = response.content if hasattr(response, "content") else str(response)

        return RewriteResult(
            original_query=query,
            rewritten_queries=[
                RewrittenQuery(query=rewritten.strip(), mode="single"),
            ],
            mode="single",
        )

    async def _multi_query_rewrite(self, query: str) -> RewriteResult:
        """多视角变体改写模式。

        生成多个不同视角的查询变体，提升检索召回率。

        Args:
            query: 原始查询。

        Returns:
            改写结果。
        """
        from langchain_core.prompts import ChatPromptTemplate

        max_variants = self.settings.query_rewriting_max_variants

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是一个查询扩展专家。请为用户的查询生成 {max_variants} 个不同视角的变体查询。"
                    "每个变体应从不同角度表达相同的检索意图。"
                    "每行输出一个变体查询，不要添加编号或解释。",
                ),
                ("human", "原始查询: {query}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke({"query": query, "max_variants": max_variants})
        content = response.content if hasattr(response, "content") else str(response)

        # 解析变体查询
        variants = [line.strip() for line in content.strip().split("\n") if line.strip()]

        # 限制变体数量
        variants = variants[:max_variants]

        rewritten_queries = [RewrittenQuery(query=v, mode="multi_query") for v in variants]

        # 始终包含原始查询
        rewritten_queries.insert(
            0, RewrittenQuery(query=query, mode="multi_query", is_original=True)
        )

        return RewriteResult(
            original_query=query,
            rewritten_queries=rewritten_queries,
            mode="multi_query",
        )

    async def _hyde_rewrite(self, query: str) -> RewriteResult:
        """HyDE 假设文档嵌入模式。

        生成一个假设性回答文档，用该文档的语义进行检索。

        Args:
            query: 原始查询。

        Returns:
            改写结果。
        """
        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "请针对用户的问题，写一段详细的假设性回答。"
                    "这段回答不需要完全准确，但应包含与问题相关的关键术语和概念。"
                    "只输出假设性回答文本，不要添加任何解释。",
                ),
                ("human", "问题: {query}"),
            ]
        )

        chain = prompt | self.llm
        response = await chain.ainvoke({"query": query})
        hyde_doc = response.content if hasattr(response, "content") else str(response)

        return RewriteResult(
            original_query=query,
            rewritten_queries=[
                RewrittenQuery(query=hyde_doc.strip(), mode="hyde"),
            ],
            mode="hyde",
        )


# 全局 QueryRewriter 实例
_query_rewriter: QueryRewriter | None = None


def get_query_rewriter() -> QueryRewriter:
    """获取 Query 改写服务单例。

    Returns:
        QueryRewriter 实例。
    """
    global _query_rewriter

    if _query_rewriter is None:
        _query_rewriter = QueryRewriter()

    return _query_rewriter
