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
# LangChain 核心
langchain>=0.3.0
langchain-anthropic>=0.3.0
langgraph>=0.2.0
langchain-community>=0.3.0
pydantic>=2.0.0

# RAG 知识库增强
asyncpg>=0.29.0              # PostgreSQL 异步驱动
sqlalchemy[asyncio]>=2.0.0   # ORM 框架
pgvector>=0.2.0              # PostgreSQL 向量扩展
sentence-transformers>=2.2.0 # Embedding 模型框架
FlagEmbedding>=1.2.0         # BGE Embedding 模型
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

## 六、RAG 知识库开发规范

### 6.1 向量数据库规范

```python
from sqlalchemy import Column, String, Text, DateTime, Integer, Float
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

class KnowledgeChunk(Base):
    """知识分块表模型。"""
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024))  # BGE-large-zh 向量维度
    metadata = Column(JSONB, default={})
    created_at = Column(DateTime, nullable=False)
```

### 6.2 Embedding 服务规范

```python
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    """BGE-large-zh Embedding 服务封装。"""

    def __init__(self, model_name: str = "BAAI/bge-large-zh") -> None:
        """初始化 Embedding 模型。

        Args:
            model_name: HuggingFace 模型名称。
        """
        self.model = SentenceTransformer(model_name)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量文档向量化。

        Args:
            texts: 文本列表。

        Returns:
            向量列表。
        """
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    async def embed_query(self, query: str) -> list[float]:
        """查询向量化。

        Args:
            query: 查询文本。

        Returns:
            查询向量。
        """
        return self.model.encode([query], normalize_embeddings=True)[0].tolist()
```

### 6.3 知识检索规范

```python
from src.rag.retriever import KnowledgeRetriever
from src.db import get_db

class RAGEnhancedAgent:
    """RAG 增强智能体基类。"""

    def __init__(self, retriever: KnowledgeRetriever | None = None) -> None:
        """初始化智能体。

        Args:
            retriever: 知识检索器实例。
        """
        self._retriever = retriever

    async def retrieve_knowledge(
        self,
        query: str,
        doc_types: list[str] | None = None,
        top_k: int = 5
    ) -> list[dict]:
        """检索相关知识。

        Args:
            query: 查询文本。
            doc_types: 文档类型过滤。
            top_k: 返回数量。

        Returns:
            检索结果列表。
        """
        if not self._retriever:
            return []

        return await self._retriever.retrieve(
            query=query,
            doc_types=doc_types,
            top_k=top_k
        )
```

### 6.4 知识库文档类型

| 类型 | 说明 | 用途 |
|------|------|------|
| `brand_guide` | 品牌规范 | 品牌调性、视觉规范、语言风格 |
| `category_knowledge` | 类目知识 | 商品特点、卖点模板、关键词 |
| `case_study` | 成功案例 | 历史优秀创意方案参考 |
| `compliance_rule` | 合规规则 | 广告法禁止词、平台审核标准 |

### 6.5 RAG 日志规范

```python
from src.rag.logger import get_rag_logger

logger = get_rag_logger()

# 记录检索操作
await logger.log_retrieval(
    session=db_session,
    task_id="task_001",
    agent_name="RequirementAnalyzer",
    query="品牌视觉规范",
    doc_types=["brand_guide"],
    top_k=5,
    results=[...],
    similarity_scores=[0.85, 0.82, ...]
)
```

---

## 七、环境配置

### 7.1 环境变量

```bash
# .env 文件
ANTHROPIC_API_KEY=your_api_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langchain_api_key  # 可选，用于 LangSmith
LANGCHAIN_PROJECT=agent-part  # 项目名称

# RAG 知识库配置
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agent_part
RAG_ENABLED=true
EMBEDDING_MODEL=BAAI/bge-large-zh  # BGE-large-zh 本地模型
EMBEDDING_DEVICE=cpu               # cpu 或 cuda
VECTOR_DIMENSION=1024              # BGE-large-zh 向量维度
RAG_TOP_K=5                        # 检索返回数量
RAG_SIMILARITY_THRESHOLD=0.5       # 相似度阈值
```

### 7.2 Python 版本

- 最低版本: Python 3.11
- 当前版本: Python 3.13

### 7.3 uv 工具使用 (强制执行)

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

## 八、代码质量检查

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

## 九、推荐技能/代理

| 场景 | 推荐使用 |
|------|----------|
| Python 代码审查 | `python-reviewer` |
| Python 最佳实践 | `python-patterns` |
| 测试驱动开发 | `tdd-guide`, `python-testing` |
| 安全审查 | `security-reviewer` |
| Agent 架构设计 | `architect`, `agent-harness-construction` |
| PyTorch 相关 | `pytorch-patterns` |
| RAG 开发 | `database-reviewer`, `architect` |

---

## 十、文档规范

### 10.1 文档存放位置

```
./documents/
├── 2026-03-22_LangChain智能体开发计划.md
├── 2026-03-22_工具系统开发计划.md
└── ...
```

### 10.2 文档模板

遵循全局配置中的 8 章节结构。

---

## 十一、快速参考

### 11.1 常用命令 (uv)

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

### 11.2 pyproject.toml 示例

```toml
[project]
name = "agent-part"
version = "0.1.0"
description = "LangChain Agent 智能体项目"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    # LangChain 核心
    "langchain>=0.3.0",
    "langchain-anthropic>=0.3.0",
    "langgraph>=0.2.0",
    "langchain-community>=0.3.0",
    "pydantic>=2.0.0",
    # RAG 知识库增强
    "asyncpg>=0.29.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "pgvector>=0.2.0",
    "sentence-transformers>=2.2.0",
    "FlagEmbedding>=1.2.0",
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

### 11.3 LangChain 文档

- 官方文档: https://python.langchain.com/
- LangGraph 文档: https://langchain-ai.github.io/langgraph/
- Anthropic API: https://docs.anthropic.com/
- uv 文档: https://docs.astral.sh/uv/

### 11.4 RAG 相关文档

- PGVector 文档: https://github.com/pgvector/pgvector
- BGE Embedding: https://huggingface.co/BAAI/bge-large-zh
- Sentence Transformers: https://www.sbert.net/
- SQLAlchemy 异步: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html