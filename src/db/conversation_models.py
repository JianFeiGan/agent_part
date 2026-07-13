"""
AI 会话记录数据库模型。

记录系统中所有 AI 会话的详细信息，包括：
- 会话元数据（关联任务、Agent、模型）
- Token 使用量（输入/输出/总计）
- 费用估算
- 会话内容（输入/输出）
"""

from datetime import datetime
from typing import Any

from sqlalchemy import ARRAY, Float, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.db.postgres import Base


class AIConversationLog(Base):
    """AI 会话记录模型。

    Attributes:
        id: 主键。
        tenant_id: 租户 ID。
        task_id: 关联的任务 ID（可选）。
        session_id: 会话 ID（同一工作流执行共享一个 session_id）。
        agent_name: Agent 名称。
        model_name: 使用的模型名称。
        provider: LLM 提供商（qwen/dashscope/claude）。
        input_content: 输入内容摘要。
        output_content: 输出内容摘要。
        input_tokens: 输入 token 数。
        output_tokens: 输出 token 数。
        total_tokens: 总 token 数。
        cost_usd: 估算费用（美元）。
        cost_cny: 估算费用（人民币）。
        latency_ms: 响应延迟（毫秒）。
        status: 会话状态（success/failed/timeout）。
        error_message: 错误信息（失败时）。
        extra_data: 额外元数据。
        created_at: 创建时间。
    """

    __tablename__ = "ai_conversation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="租户 ID"
    )
    task_id: Mapped[str | None] = mapped_column(
        String(100), index=True, comment="关联任务 ID"
    )
    session_id: Mapped[str | None] = mapped_column(
        String(100), index=True, comment="会话 ID"
    )
    agent_name: Mapped[str | None] = mapped_column(
        String(50), index=True, comment="Agent 名称"
    )
    model_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="模型名称"
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, default="qwen", comment="LLM 提供商"
    )
    input_content: Mapped[str | None] = mapped_column(
        Text, comment="输入内容摘要"
    )
    output_content: Mapped[str | None] = mapped_column(
        Text, comment="输出内容摘要"
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="输入 token 数"
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="输出 token 数"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="总 token 数"
    )
    cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="估算费用（美元）"
    )
    cost_cny: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="估算费用（人民币）"
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer, comment="响应延迟（毫秒）"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="success", index=True, comment="状态"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, comment="错误信息"
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, comment="额外元数据"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<AIConversationLog(id={self.id}, agent='{self.agent_name}', "
            f"model='{self.model_name}', tokens={self.total_tokens})>"
        )
