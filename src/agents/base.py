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
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.config.settings import Settings, get_settings

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
    ) -> None:
        """初始化Agent。

        Args:
            role: Agent角色。
            llm: 可选的语言模型实例。
            settings: 可选的配置实例。
            retriever: 可选的知识检索器，用于RAG增强。
        """
        self.role = role
        self.settings = settings or get_settings()
        self._llm = llm
        self._retriever = retriever
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
