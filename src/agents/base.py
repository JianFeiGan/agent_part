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

from src.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass

# 状态类型变量
StateT = TypeVar("StateT", bound="AgentState")


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


class AgentState(BaseModel):
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
    next_agent: AgentRole | None = Field(default=None, description="下一个要执行的Agent")


class BaseAgent(ABC, Generic[StateT]):
    """Agent基类。

    所有协作Agent的基类，提供：
    - LLM 调用封装
    - 提示模板管理
    - 工具注册
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
        self._tools: list[Any] = []
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

    async def retrieve_knowledge(
        self,
        query: str,
        doc_type: str | None = None,
        category: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """执行知识检索（RAG 增强）。

        Args:
            query: 检索查询。
            doc_type: 文档类型过滤。
            category: 类目过滤。
            top_k: 返回结果数量。

        Returns:
            检索结果列表。

        Raises:
            RuntimeError: 未配置知识检索器时抛出。
        """
        if not self.has_rag():
            return []

        # 导入 KnowledgeRetriever（延迟导入避免循环依赖）
        from src.rag.retriever import KnowledgeRetriever

        if isinstance(self._retriever, KnowledgeRetriever):
            # 需要从外部注入 session，这里返回空结果
            # 实际检索在具体 Agent 执行时通过 session 完成
            return []
        return []

    def _create_llm(self) -> BaseChatModel:
        """创建LLM实例。

        根据 llm_provider 配置选择 LLM 创建方式：
        - qwen: 使用 ChatOpenAI + 百炼 OpenAI 兼容端点
        - dashscope: 使用 ChatTongyi + DashScope SDK

        子类可重写此方法以使用不同的LLM。

        Returns:
            语言模型实例。

        Raises:
            ImportError: 缺少必要的依赖包。
            ValueError: 未配置对应的 API Key。
        """
        provider = self.settings.llm_provider

        if provider == "qwen":
            from langchain_openai import ChatOpenAI

            api_key = self.settings.effective_qwen_api_key
            if not api_key:
                raise ValueError("QWEN_API_KEY 或 DASHSCOPE_API_KEY 未配置，请检查 .env 文件")

            model_name = self.settings.qwen_llm_model
            logger.info(f"初始化千问 LLM (OpenAI兼容): model={model_name}")

            return ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=self.settings.qwen_api_base,
                temperature=0.7,
            )

        # 默认使用 DashScope SDK
        try:
            from langchain_community.chat_models import ChatTongyi

            api_key = self.settings.effective_dashscope_api_key
            if not api_key:
                raise ValueError("DASHSCOPE_API_KEY 或 QWEN_API_KEY 未配置，请检查 .env 文件")

            return ChatTongyi(
                model=self.settings.llm_model,
                dashscope_api_key=api_key,
                temperature=0.7,
            )
        except ImportError:
            raise ImportError("请安装 langchain-community: pip install langchain-community")

    def register_tool(self, tool: Any) -> None:
        """注册工具。

        Args:
            tool: 工具实例。
        """
        self._tools.append(tool)

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
            prompt_text = prompt.format(**{k: f"{{{k}}}" for k in input_vars.keys()})
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
            response = await chain.ainvoke(input_vars, **kwargs)
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


class RunnableAgent(BaseAgent[StateT]):
    """可运行的Agent实现。

    提供基本的运行能力，子类只需实现 execute 方法。
    """

    async def run(self, state: StateT) -> AgentResult:
        """运行Agent。

        Args:
            state: 当前状态。

        Returns:
            执行结果。
        """
        try:
            result = await self.execute(state)
            return result
        except Exception as e:
            return AgentResult(
                success=False,
                error=str(e),
                next_agent=None,
            )
