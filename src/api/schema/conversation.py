"""
AI 会话记录 API Schema。
"""

from datetime import datetime

from pydantic import BaseModel, Field


# ==================== 查询参数 ====================


class ConversationQueryParams(BaseModel):
    """会话记录查询参数。"""

    agent_name: str | None = Field(default=None, description="Agent 名称过滤")
    model_name: str | None = Field(default=None, description="模型名称过滤")
    provider: str | None = Field(default=None, description="LLM 提供商过滤")
    task_id: str | None = Field(default=None, description="关联任务 ID 过滤")
    session_id: str | None = Field(default=None, description="会话 ID 过滤")
    status: str | None = Field(default=None, description="状态过滤: success/failed/timeout")
    start_date: datetime | None = Field(default=None, description="开始时间")
    end_date: datetime | None = Field(default=None, description="结束时间")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")


class ConversationContentQuery(BaseModel):
    """会话内容查询参数。"""

    keyword: str = Field(description="搜索关键词")
    search_field: str = Field(
        default="both",
        description="搜索字段: input/output/both",
    )
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=20, ge=1, le=100, description="每页大小")


# ==================== 响应模型 ====================


class ConversationLogResponse(BaseModel):
    """会话记录响应。"""

    id: int
    task_id: str | None
    session_id: str | None
    agent_name: str | None
    model_name: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cost_cny: float
    latency_ms: int | None
    status: str
    created_at: datetime


class ConversationDetailResponse(ConversationLogResponse):
    """会话记录详情（含内容）。"""

    input_content: str | None
    output_content: str | None
    error_message: str | None
    extra_data: dict | None = None


class ConversationListResponse(BaseModel):
    """会话记录列表响应。"""

    items: list[ConversationLogResponse]
    total: int
    page: int
    page_size: int


class TokenUsageStats(BaseModel):
    """Token 使用统计。"""

    total_input_tokens: int = Field(default=0, description="总输入 token")
    total_output_tokens: int = Field(default=0, description="总输出 token")
    total_tokens: int = Field(default=0, description="总 token")
    total_cost_usd: float = Field(default=0.0, description="总费用（美元）")
    total_cost_cny: float = Field(default=0.0, description="总费用（人民币）")
    avg_latency_ms: float = Field(default=0.0, description="平均延迟（毫秒）")
    success_count: int = Field(default=0, description="成功次数")
    failed_count: int = Field(default=0, description="失败次数")
    total_count: int = Field(default=0, description="总次数")


class ModelUsageBreakdown(BaseModel):
    """按模型的使用量分解。"""

    model_name: str
    provider: str
    call_count: int
    total_tokens: int
    total_cost_usd: float
    total_cost_cny: float


class AgentUsageBreakdown(BaseModel):
    """按 Agent 的使用量分解。"""

    agent_name: str
    call_count: int
    total_tokens: int
    total_cost_usd: float
    total_cost_cny: float


class UsageOverviewResponse(BaseModel):
    """使用量概览响应。"""

    stats: TokenUsageStats
    by_model: list[ModelUsageBreakdown]
    by_agent: list[AgentUsageBreakdown]


class CostBudgetRequest(BaseModel):
    """费用预算请求。"""

    daily_budget_cny: float = Field(
        default=100.0, gt=0, description="每日预算（人民币）"
    )
    monthly_budget_cny: float = Field(
        default=3000.0, gt=0, description="每月预算（人民币）"
    )


class CostBudgetResponse(BaseModel):
    """费用预算响应。"""

    today_cost_cny: float = Field(description="今日已用费用（人民币）")
    today_cost_usd: float = Field(description="今日已用费用（美元）")
    today_token_count: int = Field(description="今日 token 使用量")
    today_call_count: int = Field(description="今日调用次数")
    daily_budget_cny: float = Field(description="每日预算（人民币）")
    daily_remaining_cny: float = Field(description="每日剩余预算（人民币）")
    daily_usage_percent: float = Field(description="每日预算使用百分比")
    month_cost_cny: float = Field(description="本月已用费用（人民币）")
    monthly_budget_cny: float = Field(description="每月预算（人民币）")
    monthly_remaining_cny: float = Field(description="每月剩余预算（人民币）")
    monthly_usage_percent: float = Field(description="每月预算使用百分比")
    projected_month_cost_cny: float = Field(description="预估月费用（人民币）")
