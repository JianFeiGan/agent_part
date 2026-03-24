# LangChain Agent 智能体项目 - 项目规则

> **项目类型**: Python LangChain Agent 智能体开发
> **Python 版本**: 3.13
> **优先级**: 项目规则 > 全局规则

---

## 一、项目概述

本项目专注于 LangChain/LangGraph 智能体开发，包括：
- LangChain 链式调用与提示模板
- LangGraph 状态图智能体
- 工具定义与工具调用
- RAG 检索增强生成
- 记忆系统与对话管理

---

## 二、LangChain 开发规范 (强制执行)

### 2.1 核心依赖

```txt
langchain>=0.3.0
langchain-anthropic>=0.3.0
langgraph>=0.2.0
langchain-community>=0.3.0
pydantic>=2.0.0
```

### 2.2 导入规范

```python
# LangChain 核心组件
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# LangChain Anthropic
from langchain_anthropic import ChatAnthropic

# LangGraph
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
```

### 2.3 链式调用模式

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser

class AnswerChain:
    """问答链封装。"""

    def __init__(self, model: str = "claude-3-5-sonnet-20241022") -> None:
        """初始化问答链。

        Args:
            model: 使用的模型名称。
        """
        self.llm = ChatAnthropic(model=model)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个专业的助手。"),
            ("human", "{question}")
        ])
        self.chain = self.prompt | self.llm | StrOutputParser()

    async def invoke(self, question: str) -> str:
        """执行问答。

        Args:
            question: 用户问题。

        Returns:
            模型生成的回答。
        """
        return await self.chain.ainvoke({"question": question})
```

### 2.4 工具定义规范

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    """搜索工具输入参数。"""
    query: str = Field(description="搜索查询关键词")
    max_results: int = Field(default=5, description="最大返回结果数")

@tool(args_schema=SearchInput)
def search_tool(query: str, max_results: int = 5) -> list[dict]:
    """搜索工具，用于查找相关信息。

    Args:
        query: 搜索关键词。
        max_results: 最大返回结果数。

    Returns:
        搜索结果列表。
    """
    # 实现搜索逻辑
    return []

# 工具注册
tools = [search_tool]
```

### 2.5 LangGraph 状态图模式

```python
from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

class AgentState(TypedDict):
    """智能体状态。"""
    messages: list[dict]
    current_step: str
    tool_calls: list[dict]

class AgentGraph:
    """基于 LangGraph 的智能体。"""

    def __init__(self) -> None:
        """初始化智能体图。"""
        self.graph = StateGraph(AgentState)
        self._build_graph()
        self.checkpointer = MemorySaver()
        self.app = self.graph.compile(checkpointer=self.checkpointer)

    def _build_graph(self) -> None:
        """构建状态图。"""
        self.graph.add_node("agent", self._agent_node)
        self.graph.add_node("tools", self._tools_node)
        self.graph.add_edge("agent", "tools")
        self.graph.add_edge("tools", END)
        self.graph.set_entry_point("agent")

    async def _agent_node(self, state: AgentState) -> AgentState:
        """智能体节点处理。"""
        # 实现智能体逻辑
        return state

    async def _tools_node(self, state: AgentState) -> AgentState:
        """工具节点处理。"""
        # 实现工具调用逻辑
        return state

    async def run(self, message: str, thread_id: str = "default") -> dict:
        """运行智能体。

        Args:
            message: 用户消息。
            thread_id: 会话线程 ID。

        Returns:
            执行结果。
        """
        config = {"configurable": {"thread_id": thread_id}}
        return await self.app.ainvoke(
            {"messages": [{"role": "user", "content": message}]},
            config=config
        )
```

---

## 三、Python 编码规范 (强制执行)

### 3.1 基础规范

| 规范 | 说明 |
|------|------|
| 代码风格 | 遵循 PEP 8，使用 `ruff format` 格式化 |
| 类型注解 | **强制使用** type hints，所有公共函数必须有类型注解 |
| 文档字符串 | 使用 Google 风格 docstring |
| 导入顺序 | 标准库 → 第三方库 → LangChain → 本地模块 |

### 3.2 类和函数注释模板

```python
class RAGPipeline:
    """RAG 检索增强生成管道。

    整合文档检索和生成回答的完整流程。

    Attributes:
        retriever: 文档检索器。
        llm: 语言模型实例。
        prompt_template: 提示模板。

    Example:
        >>> pipeline = RAGPipeline(retriever=vector_store.as_retriever())
        >>> answer = await pipeline.query("什么是 Agent?")
    """

    def __init__(
        self,
        retriever: VectorStoreRetriever,
        llm: ChatAnthropic | None = None
    ) -> None:
        """初始化 RAG 管道。

        Args:
            retriever: 文档检索器实例。
            llm: 可选的语言模型，默认使用 Claude 3.5 Sonnet。
        """
        self.retriever = retriever
        self.llm = llm or ChatAnthropic(model="claude-3-5-sonnet-20241022")

    async def query(self, question: str) -> str:
        """执行查询并生成回答。

        Args:
            question: 用户问题。

        Returns:
            基于检索内容生成的回答。
        """
        pass
```

### 3.3 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块 | 小写下划线 | `agent_chain.py` |
| 类 | 大驼峰 | `AgentChain`, `RAGPipeline` |
| 函数/方法 | 小写下划线 | `process_message()` |
| 常量 | 全大写下划线 | `MAX_TOKENS` |
| 私有属性 | 单下划线前缀 | `_internal_state` |

---

## 四、测试规范 (强制执行)

### 4.1 测试要求

| 要求 | 说明 |
|------|------|
| 框架 | pytest + pytest-asyncio |
| 覆盖率 | **≥ 80%**，核心链和工具 100% |
| Mock | 使用 `pytest-mock` mock LLM 调用 |

### 4.2 LangChain 测试示例

```python
import pytest
from unittest.mock import AsyncMock, patch
from langchain_core.messages import AIMessage

class TestAnswerChain:
    """AnswerChain 测试类。"""

    @pytest.fixture
    def chain(self) -> AnswerChain:
        """创建测试用链实例。"""
        return AnswerChain()

    @pytest.mark.asyncio
    async def test_invoke(self, chain: AnswerChain) -> None:
        """测试链调用。"""
        with patch.object(chain.llm, "ainvoke", new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = AIMessage(content="测试回答")

            result = await chain.invoke("测试问题")

            assert result == "测试回答"
            mock_llm.assert_called_once()
```

### 4.3 运行测试 (使用 uv)

```bash
# 运行所有测试
uv run pytest

# 带覆盖率报告
uv run pytest --cov=src --cov-report=html

# 异步测试
uv run pytest -v --asyncio-mode=auto

# 指定测试文件
uv run pytest tests/test_agent.py -v
```

---

## 五、LangChain 特定规则

### 5.1 模型配置

```python
import os
from langchain_anthropic import ChatAnthropic

# 从环境变量读取 API Key
llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    temperature=0.7,
    max_tokens=4096
)
```

### 5.2 提示模板规范

```python
from langchain_core.prompts import ChatPromptTemplate, FewShotPromptTemplate

# 系统提示 + 用户输入
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的 {domain} 助手。请用中文回答。"),
    ("human", "{question}")
])

# Few-shot 示例
examples = [
    {"input": "你好", "output": "你好！有什么可以帮助你的吗？"},
    {"input": "再见", "output": "再见！期待下次交流。"}
]
```

### 5.3 错误处理

```python
from langchain_core.exceptions import OutputParserException

class AgentError(Exception):
    """智能体基础异常。"""
    pass

class ToolExecutionError(AgentError):
    """工具执行错误。"""
    def __init__(self, tool_name: str, original_error: Exception) -> None:
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' failed: {original_error}")

async def safe_tool_call(tool, *args, **kwargs):
    """安全工具调用包装器。"""
    try:
        return await tool.ainvoke(*args, **kwargs)
    except Exception as e:
        raise ToolExecutionError(tool.name, e) from e
```

### 5.4 回调与追踪

```python
from langchain.callbacks.tracers import LangChainTracer

# 启用 LangSmith 追踪（需配置环境变量）
tracer = LangChainTracer()

# 在链中使用
result = await chain.ainvoke(
    {"question": "测试问题"},
    config={"callbacks": [tracer]}
)
```

---

## 六、环境配置

### 6.1 环境变量

```bash
# .env 文件
ANTHROPIC_API_KEY=your_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key  # 可选，用于 LangSmith
LANGCHAIN_PROJECT=agent-part  # 项目名称
```

### 6.2 Python 版本

- 最低版本: Python 3.11
- 当前版本: Python 3.13

### 6.3 uv 工具使用 (强制执行)

本项目使用 **uv** 进行 Python 环境管理，替代传统的 pip/poetry。

```bash
# 初始化项目（创建虚拟环境）
uv venv

# 激活虚拟环境
source .venv/bin/activate  # macOS/Linux

# 安装依赖
uv pip install -r pyproject.toml

# 添加新依赖
uv add langchain langchain-anthropic langgraph

# 添加开发依赖
uv add --dev pytest pytest-asyncio pytest-mock ruff mypy

# 同步依赖（根据 lock 文件）
uv sync

# 运行脚本
uv run python main.py

# 运行测试
uv run pytest
```

---

## 七、代码质量检查

```bash
# 格式化
uv run ruff format .

# Lint 检查
uv run ruff check .

# 类型检查
uv run mypy src/

# 完整检查
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest --cov
```

---

## 八、推荐技能/代理

| 场景 | 推荐使用 |
|------|----------|
| Python 代码审查 | `python-reviewer` |
| Python 最佳实践 | `python-patterns` |
| 测试驱动开发 | `tdd-guide`, `python-testing` |
| 安全审查 | `security-reviewer` |
| Agent 架构设计 | `architect`, `agent-harness-construction` |
| PyTorch 相关 | `pytorch-patterns` |

---

## 九、文档规范

### 9.1 文档存放位置

```
./documents/
├── 2026-03-22_LangChain智能体开发计划.md
├── 2026-03-22_工具系统开发计划.md
└── ...
```

### 9.2 文档模板

遵循全局配置中的 8 章节结构。

---

## 十、快速参考

### 10.1 常用命令 (uv)

```bash
# 创建虚拟环境
uv venv

# 安装依赖
uv sync

# 添加新依赖
uv add <package-name>

# 运行主程序
uv run python main.py

# 运行测试
uv run pytest

# 带覆盖率测试
uv run pytest --cov=src --cov-report=html

# 格式化代码
uv run ruff format .

# Lint 检查
uv run ruff check .

# 类型检查
uv run mypy src/

# 完整检查流程
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest --cov
```

### 10.2 pyproject.toml 示例

```toml
[project]
name = "agent-part"
version = "0.1.0"
description = "LangChain Agent 智能体项目"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "langchain>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langgraph>=0.2.0",
    "langchain-community>=0.3.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-mock>=3.12.0",
    "pytest-cov>=4.1.0",
    "ruff>=0.3.0",
    "mypy>=1.8.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 10.3 LangChain 文档

- 官方文档: https://python.langchain.com/
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- Anthropic API: https://docs.anthropic.com/
- uv 文档: https://docs.astral.sh/uv/