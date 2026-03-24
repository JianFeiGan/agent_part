"""
Agent基类模块。

Description:
    定义所有Agent的基类和通用接口，提供统一的LLM调用、工具管理等能力。
@author ganjianfei
@version 1.0.0
2026-03-23
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.config.settings import Settings, get_settings

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
    messages: list[BaseMessage] = Field(
        default_factory=list, description="消息历史"
    )
    error: str | None = Field(default=None, description="错误信息")
    next_agent: AgentRole | None = Field(
        default=None, description="下一个要执行的Agent"
    )


class BaseAgent(ABC, Generic[StateT]):
    """Agent基类。

    所有协作Agent的基类，提供：
    - LLM 调用封装
    - 提示模板管理
    - 工具注册
    - 状态管理

    Attributes:
        role: Agent角色。
        llm: 语言模型实例。
        settings: 配置实例。
        tools: 工具列表。

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
    ) -> None:
        """初始化Agent。

        Args:
            role: Agent角色。
            llm: 可选的语言模型实例。
            settings: 可选的配置实例。
        """
        self.role = role
        self.settings = settings or get_settings()
        self._llm = llm
        self._tools: list[Any] = []
        self._prompts: dict[str, ChatPromptTemplate] = {}

    @property
    def llm(self) -> BaseChatModel:
        """获取LLM实例（延迟初始化）。

        Returns:
            语言模型实例。
        """
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm

    def _create_llm(self) -> BaseChatModel:
        """创建LLM实例。

        子类可重写此方法以使用不同的LLM。

        Returns:
            语言模型实例。
        """
        # 默认使用通义千问
        try:
            from langchain_community.chat_models import ChatTongyi

            return ChatTongyi(
                model=self.settings.llm_model,
                dashscope_api_key=self.settings.dashscope_api_key,
                temperature=0.7,
            )
        except ImportError:
            raise ImportError(
                "请安装 langchain-community: pip install langchain-community"
            )

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
        """调用LLM生成响应。

        Args:
            prompt: 提示模板。
            input_vars: 输入变量。
            **kwargs: 其他参数。

        Returns:
            生成的响应文本。
        """
        chain = prompt | self.llm
        response = await chain.ainvoke(input_vars, **kwargs)
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
