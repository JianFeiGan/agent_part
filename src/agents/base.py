"""
Agent基类模块。

Description:
    定义所有Agent的基类和通用接口，提供统一的LLM调用、工具管理等能力。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass

# 状态类型变量
StateT = TypeVar("StateT", bound="AgentRuntimeState")


class AgentRole(str, Enum):
    """Agent角色枚举。"""

    ORCHESTRATOR = "orchestrator"
    REQUIREMENT_ANALYZER = "requirement_analyzer"
    CREATIVE_PLANNER = "creative_planner"
    VISUAL_DESIGNER = "visual_designer"
    IMAGE_GENERATOR = "image_generator"
    VIDEO_GENERATOR = "video_generator"
    QUALITY_REVIEWER = "quality_reviewer"


class AgentStatus(str, Enum):
    """Agent状态枚举。"""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRuntimeState(BaseModel):
    """Agent状态基类。"""

    agent_id: str = Field(..., description="Agent ID")
    role: AgentRole = Field(..., description="Agent角色")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="当前状态")
    current_task: str | None = Field(default=None, description="当前任务")
    error: str | None = Field(default=None, description="错误信息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class AgentResult(BaseModel):
    """Agent执行结果。"""

    success: bool = Field(..., description="是否成功")
    data: dict[str, Any] = Field(default_factory=dict, description="结果数据")
    messages: list[BaseMessage] = Field(default_factory=list, description="消息历史")
    error: str | None = Field(default=None, description="错误信息")


class BaseAgent(ABC, Generic[StateT]):
    """Agent基类。

    所有协作Agent的基类，提供：
    - LLM 调用封装
    - 提示模板管理
    - 状态管理
    - RAG 知识检索（可选）

    Attributes:
        role: Agent角色。
        llm: 语言模型实例。
        settings: 配置实例。
        tools: 工具列表。
        retriever: 知识检索器（可选，用于RAG增强）。

    Example:
        >>> class MyAgent(BaseAgent[MyState]):
        ...     async def execute(self, state: MyState) -> AgentResult:
        ...         # 实现具体逻辑
        ...         pass
    """

    def __init__(
        self,
        role: AgentRole,
        llm: BaseChatModel | None = None,
        settings: Settings | None = None,
        retriever: Any | None = None,  # KnowledgeRetriever 类型，使用 Any 避免循环导入
        tenant_id: str = "system",
        task_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """初始化Agent。

        Args:
            role: Agent角色。
            llm: 可选的语言模型实例。
            settings: 可选的配置实例。
            retriever: 可选的知识检索器，用于RAG增强。
            tenant_id: 租户 ID，用于会话记录隔离。
            task_id: 关联任务 ID，用于会话记录关联。
            session_id: 会话 ID，用于同一工作流的 LLM 调用关联。
        """
        self.role = role
        self.settings = settings or get_settings()
        self._llm = llm
        self._retriever = retriever
        self._tenant_id = tenant_id
        self._task_id = task_id
        self._session_id = session_id
        self._prompts: dict[str, ChatPromptTemplate] = {}
        self._last_trace: dict[str, Any] | None = None

    @property
    def llm(self) -> BaseChatModel:
        """获取LLM实例（延迟初始化）。

        Returns:
            语言模型实例。
        """
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    @property
    def retriever(self) -> Any | None:
        """获取知识检索器。

        Returns:
            知识检索器实例，未配置则返回 None。
        """
        return self._retriever

    def has_rag(self) -> bool:
        """检查是否配置了 RAG 检索器。

        Returns:
            是否有 RAG 能力。
        """
        return self._retriever is not None and self.settings.rag_enabled

    def _create_llm(self) -> BaseChatModel:
        """创建LLM实例（配置驱动）。

        通过 ProviderFactory 获取 LLM Provider，优先从数据库配置，
        兜底使用 Settings 环境变量。不再硬编码 ChatTongyi。

        Returns:
            语言模型实例。

        Raises:
            ImportError: 未配置任何 LLM Provider 时抛出。
        """
        from src.clients.openai_compatible_llm import SettingsFallbackLLMProvider

        provider = SettingsFallbackLLMProvider(settings=self.settings)
        if provider.is_available():
            return provider.create_chat_model()

        raise ImportError(
            "未配置任何 LLM Provider。"
            "请在模型厂商管理页面配置，或设置 DASHSCOPE_API_KEY / SENSENOVA_API_KEY 环境变量。"
        )

    def register_prompt(self, name: str, template: ChatPromptTemplate) -> None:
        """注册提示模板。

        Args:
            name: 模板名称。
            template: 提示模板。
        """
        self._prompts[name] = template

    def get_prompt(self, name: str) -> ChatPromptTemplate | None:
        """获取提示模板。

        Args:
            name: 模板名称。

        Returns:
            提示模板，不存在则返回 None。
        """
        return self._prompts.get(name)

    @abstractmethod
    async def execute(self, state: StateT) -> AgentResult:
        """执行Agent任务。

        子类必须实现此方法。

        Args:
            state: 当前状态。

        Returns:
            执行结果。
        """
        pass

    async def _ainvoke_with_retry(
        self,
        chain: Any,
        input_vars: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """调用 LLM 链，按配置进行指数退避重试。

        仅捕获 Exception（网络抖动、限流等瞬态错误）；
        asyncio.CancelledError 等取消信号不会被重试拦截。

        Args:
            chain: LangChain LCEL 链。
            input_vars: 输入变量。
            **kwargs: 透传给链的参数。

        Returns:
            模型响应。
        """
        attempts = max(1, self.settings.llm_retry_attempts + 1)

        def _log_retry(retry_state: Any) -> None:
            exc = (
                retry_state.outcome.exception()
                if retry_state.outcome and retry_state.outcome.failed
                else "unknown"
            )
            logger.warning(
                "LLM 调用失败，准备第 %s/%s 次尝试（退避 %.1fs）: %s",
                retry_state.attempt_number,
                attempts,
                self.settings.llm_retry_initial_backoff * (2 ** (retry_state.attempt_number - 1)),
                exc,
            )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=self.settings.llm_retry_initial_backoff),
            before_sleep=_log_retry,
            reraise=True,
        ):
            with attempt:
                return await chain.ainvoke(input_vars, **kwargs)
        raise RuntimeError("unreachable")  # AsyncRetrying 循环必然 return 或抛出

    async def invoke_llm(
        self,
        prompt: ChatPromptTemplate,
        input_vars: dict[str, Any],
        **kwargs: Any,
    ) -> str:
        """调用LLM生成响应，并自动记录会话信息和 Trace 数据。

        Trace 数据会存储到 self._last_trace 中，供 Agent 节点回写到 AgentLog。

        Args:
            prompt: 提示模板。
            input_vars: 输入变量。
            **kwargs: 其他参数。

        Returns:
            生成的响应文本。
        """
        from src.api.service.conversation_recorder import ConversationRecorder

        # 构建输入内容摘要
        input_summary = str(input_vars)[:2000] if input_vars else ""

        # 获取模型名称
        model_name = getattr(self.llm, "model_name", getattr(self.llm, "model", "unknown"))

        # 提取提示词模板文本
        prompt_text = ""
        try:
            prompt_text = prompt.format(**{k: f"{{{k}}}" for k in input_vars})
        except Exception:
            prompt_text = str(prompt)

        async with ConversationRecorder(
            tenant_id=self._tenant_id,
            task_id=self._task_id,
            session_id=self._session_id,
            agent_name=self.role.value,
            model_name=model_name,
            provider=self.settings.llm_provider,
            input_content=input_summary,
        ) as recorder:
            chain = prompt | self.llm
            response = await self._ainvoke_with_retry(chain, input_vars, **kwargs)
            recorder.set_response(response)

            # 保存 Trace 数据，供 Agent 节点回写到 AgentLog
            self._last_trace = {
                "prompt_template": prompt_text[:5000],
                "prompt_variables": {k: str(v)[:500] for k, v in input_vars.items()},
                "input_tokens": recorder._input_tokens,
                "output_tokens": recorder._output_tokens,
                "total_tokens": recorder._input_tokens + recorder._output_tokens,
                "cost_cny": 0.0,
                "model_name": model_name,
                "provider": self.settings.llm_provider,
                "latency_ms": int((recorder._start_time and __import__("time").monotonic() - recorder._start_time) * 1000) if recorder._start_time else None,
            }
            # 计算费用
            from src.api.service.conversation_recorder import _calculate_cost
            cost_usd, cost_cny = _calculate_cost(
                model_name, recorder._input_tokens, recorder._output_tokens
            )
            self._last_trace["cost_cny"] = round(cost_cny, 4)

            return response.content if hasattr(response, "content") else str(response)

    def __repr__(self) -> str:
        """返回Agent描述。

        Returns:
            Agent描述字符串。
        """
        return f"{self.__class__.__name__}(role={self.role.value})"
