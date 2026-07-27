"""
AI 会话记录服务。

自动记录 LLM 调用的 token 使用量、延迟和费用。
"""

import logging
import time
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.config.settings import get_settings
from src.db.conversation_models import AIConversationLog
from src.db.postgres import get_db_session
from src.db.repository import BaseRepository

logger = logging.getLogger(__name__)

# ==================== 模型定价表（每千 token，美元） ====================
# 参考：https://help.aliyun.com/zh/model-studio/getting-started/models

MODEL_PRICING: dict[str, dict[str, float]] = {
    # 千问系列
    "qwen-plus": {"input": 0.0008, "output": 0.002, "currency": "usd"},
    "qwen-turbo": {"input": 0.0003, "output": 0.0006, "currency": "usd"},
    "qwen-max": {"input": 0.004, "output": 0.012, "currency": "usd"},
    "qwen-long": {"input": 0.0005, "output": 0.002, "currency": "usd"},
    "qwen3.5-flash": {"input": 0.0003, "output": 0.0006, "currency": "usd"},
    # 通义万象图片
    "wanx-v1": {"input": 0.08, "output": 0.0, "currency": "usd"},  # 按次计费
    # 可灵视频
    "kling-v1": {"input": 0.50, "output": 0.0, "currency": "usd"},  # 按次计费
}

# USD/CNY 汇率
USD_CNY_RATE = 7.2

# 默认定价（模型不在定价表中时使用）
DEFAULT_PRICING: dict[str, float] = {"input": 0.001, "output": 0.002, "currency": "usd"}


def _calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> tuple[float, float]:
    """计算 token 费用。

    Args:
        model_name: 模型名称。
        input_tokens: 输入 token 数。
        output_tokens: 输出 token 数。

    Returns:
        (cost_usd, cost_cny) 元组。
    """
    pricing = MODEL_PRICING.get(model_name, DEFAULT_PRICING)
    input_cost = (input_tokens / 1000.0) * pricing["input"]
    output_cost = (output_tokens / 1000.0) * pricing["output"]
    cost_usd = input_cost + output_cost
    cost_cny = cost_usd * USD_CNY_RATE
    return cost_usd, cost_cny


async def record_conversation(
    *,
    tenant_id: str,
    task_id: str | None = None,
    session_id: str | None = None,
    agent_name: str | None = None,
    model_name: str,
    provider: str = "qwen",
    input_content: str | None = None,
    output_content: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int | None = None,
    status: str = "success",
    error_message: str | None = None,
    extra_data: dict[str, Any] | None = None,
) -> AIConversationLog | None:
    """记录一次 AI 会话。

    Args:
        tenant_id: 租户 ID。
        task_id: 关联任务 ID。
        session_id: 会话 ID。
        agent_name: Agent 名称。
        model_name: 模型名称。
        provider: LLM 提供商。
        input_content: 输入内容摘要。
        output_content: 输出内容摘要。
        input_tokens: 输入 token 数。
        output_tokens: 输出 token 数。
        latency_ms: 响应延迟。
        status: 会话状态。
        error_message: 错误信息。
        extra_data: 额外元数据。

    Returns:
        创建的会话记录，数据库不可用时返回 None。
    """
    total_tokens = input_tokens + output_tokens
    cost_usd, cost_cny = _calculate_cost(model_name, input_tokens, output_tokens)

    # 截断长内容，避免数据库存储过大
    max_content_len = 5000
    if input_content and len(input_content) > max_content_len:
        input_content = input_content[:max_content_len] + "...(已截断)"
    if output_content and len(output_content) > max_content_len:
        output_content = output_content[:max_content_len] + "...(已截断)"

    try:
        async with get_db_session() as session:
            repo = BaseRepository(AIConversationLog, session)
            log = await repo.create(
                tenant_id=tenant_id,
                task_id=task_id,
                session_id=session_id,
                agent_name=agent_name,
                model_name=model_name,
                provider=provider,
                input_content=input_content,
                output_content=output_content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                cost_cny=cost_cny,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
                extra_data=extra_data or {},
            )
            return log
    except Exception as e:
        # 记录失败不应阻断业务流程
        logger.warning(f"AI 会话记录失败: {e}")
        return None


class ConversationRecorder:
    """LLM 调用记录器。

    用作上下文管理器，自动记录 LLM 调用的 token 使用和延迟。

    Example:
        >>> async with ConversationRecorder(
        ...     tenant_id="dev",
        ...     agent_name="OrchestratorAgent",
        ...     model_name="qwen-plus",
        ... ) as recorder:
        ...     response = await llm.ainvoke(prompt)
        ...     recorder.set_response(response)
    """

    def __init__(
        self,
        *,
        tenant_id: str = "system",
        task_id: str | None = None,
        session_id: str | None = None,
        agent_name: str | None = None,
        model_name: str = "qwen-plus",
        provider: str = "qwen",
        input_content: str | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._task_id = task_id
        self._session_id = session_id
        self._agent_name = agent_name
        self._model_name = model_name
        self._provider = provider
        self._input_content = input_content
        self._start_time: float = 0
        self._output_content: str | None = None
        self._input_tokens: int = 0
        self._output_tokens: int = 0
        self._status: str = "success"
        self._error_message: str | None = None

    async def __aenter__(self) -> "ConversationRecorder":
        self._start_time = time.monotonic()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        latency_ms = int((time.monotonic() - self._start_time) * 1000)

        if exc_type is not None:
            self._status = "failed"
            self._error_message = str(exc_val)[:2000]

        try:
            await record_conversation(
                tenant_id=self._tenant_id,
                task_id=self._task_id,
                session_id=self._session_id,
                agent_name=self._agent_name,
                model_name=self._model_name,
                provider=self._provider,
                input_content=self._input_content,
                output_content=self._output_content,
                input_tokens=self._input_tokens,
                output_tokens=self._output_tokens,
                latency_ms=latency_ms,
                status=self._status,
                error_message=self._error_message,
            )
        except Exception as e:
            # 记录失败绝不影响原始异常传播
            logger.warning(f"AI 会话记录写入失败: {e}")

        return False  # 不抑制异常

    def set_response(self, response: Any) -> None:
        """设置 LLM 响应，自动提取 token 使用量。"""
        content = getattr(response, "content", str(response))
        # AIMessage.content 在多模态响应时可能为 list，转为字符串
        if isinstance(content, list):
            content = str(content)
        self._output_content = content

        # 尝试从 usage_metadata 提取 token 使用量
        # LangChain AIMessage.usage_metadata 可能是 UsageMetadata pydantic 对象或 dict
        usage_metadata = getattr(response, "usage_metadata", None)
        if usage_metadata:
            if isinstance(usage_metadata, dict):
                self._input_tokens = usage_metadata.get("input_tokens", 0)
                self._output_tokens = usage_metadata.get("output_tokens", 0)
            else:
                # UsageMetadata pydantic/dataclass 对象，使用 getattr
                self._input_tokens = getattr(usage_metadata, "input_tokens", 0) or 0
                self._output_tokens = getattr(usage_metadata, "output_tokens", 0) or 0
        else:
            # 从 response_metadata 提取（OpenAI 兼容模式 / DashScope SDK）
            response_metadata = getattr(response, "response_metadata", {})
            if isinstance(response_metadata, dict):
                # ChatOpenAI: token_usage; ChatTongyi: usage
                token_usage = response_metadata.get("token_usage") or response_metadata.get("usage") or {}
                if token_usage:
                    self._input_tokens = token_usage.get("prompt_tokens", 0)
                    self._output_tokens = token_usage.get("completion_tokens", 0)
