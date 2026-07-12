# agent_part 项目规则

> **项目类型**: Python LangChain Agent + Vue 3 前端
> **Python 版本**: 3.11+
> **包管理**: uv
> **优先级**: 项目规则 > 全局规则

---

## 一、项目概述

基于 LangChain/LangGraph 的多 Agent 协作商品视觉内容生成系统。

核心能力：
- 多 Agent 协作 (7 个专业 Agent)
- 图片/视频智能生成
- RAG 知识增强
- 质量自动审核

---

## 二、技术栈

| 层级 | 技术 |
|------|------|
| LLM 框架 | LangChain 0.3+, LangGraph 0.2+ |
| 主力 LLM | 通义千问 (qwen3.5-flash) |
| 图像生成 | 通义万象 (wanx-v1) |
| 视频生成 | 可灵 AI (kling-v1) |
| 向量数据库 | PostgreSQL + PGVector |
| Embedding | BGE-large-zh |
| API 框架 | FastAPI |
| 前端 | Vue 3 + TypeScript + Element Plus |

---

## 三、Python 开发规范

| 规范 | 要求 |
|------|------|
| 代码风格 | PEP 8, ruff format |
| 类型注解 | 强制使用，所有公共函数必须有 |
| Docstring | Google 风格 |
| 行长度 | 最大 100 字符 |
| 导入顺序 | 标准库 → 第三方 → LangChain → 本地 |

命名规范：
- 模块: snake_case
- 类: PascalCase
- 函数/方法: snake_case
- 常量: UPPER_SNAKE_CASE
- 私有属性: _leading_underscore

---

## 四、LangChain/LangGraph 规范

### 4.1 导入路径

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langgraph.graph import StateGraph, END
```

### 4.2 核心模式

| 模式 | 说明 |
|------|------|
| 链式调用 | `prompt | llm | parser` |
| 状态累加 | `Annotated[list, add]` |
| 工具定义 | `@tool` + `args_schema` (Pydantic BaseModel) |

---

## 五、测试规范

| 配置 | 值 |
|------|------|
| 框架 | pytest + pytest-asyncio |
| 覆盖率要求 | ≥ 80% |
| asyncio_mode | auto |
| Mock | pytest-mock |

测试命令：
- `uv run pytest` - 运行测试
- `uv run pytest --cov=src` - 带覆盖率
- `uv run pytest -v --asyncio-mode=auto` - 异步测试

---

## 六、代码质量命令

```bash
uv run ruff format .      # 格式化
uv run ruff check .       # Lint 检查
uv run mypy src/          # 类型检查
uv run pytest --cov       # 测试 + 覆盖率
```

完整检查流程：
```bash
uv run ruff format . && uv run ruff check . && uv run mypy src/ && uv run pytest --cov
```

---

## 七、提交规范

使用 Conventional Commits：
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具变更

示例：
```
feat: add support for NewImageProvider client
fix: handle provider timeout in agent fallback logic
```

---

## 八、环境配置

关键环境变量：
- `DASHSCOPE_API_KEY` - 必填，阿里云 DashScope API Key
- `KLING_ACCESS_KEY` / `KLING_SECRET_KEY` - 必填，可灵 AI 密钥
- `RAG_ENABLED` - 是否启用 RAG (true/false)
- `EMBEDDING_MODEL` - BAAI/bge-large-zh
- `POSTGRES_HOST` / `POSTGRES_PORT` - PostgreSQL 连接

---

## 九、RAG 规范

知识库文档类型：
| 类型 | 说明 |
|------|------|
| `brand_guide` | 品牌规范 |
| `category_knowledge` | 类目知识 |
| `case_study` | 成功案例 |
| `compliance_rule` | 合规规则 |

Embedding 配置：
- 模型: BAAI/bge-large-zh
- 向量维度: 1024
- 存储: PGVector

---

## 十、前端规范

| 配置 | 值 |
|------|------|
| 框架 | Vue 3 + TypeScript |
| 构建工具 | Vite 5 |
| 状态管理 | Pinia |
| UI 库 | Element Plus |
| TypeScript | strict mode |

前端命令：
- `npm run dev` - 开发服务器
- `npm run build` - 构建（vue-tsc + vite build）
- `npm run lint` - ESLint 检查