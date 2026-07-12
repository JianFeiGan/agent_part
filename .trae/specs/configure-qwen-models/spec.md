# 新增千问系列模型支持 Spec

## Why
当前项目支持多个模型提供商（DashScope、可灵AI等），用户希望新增千问系列模型作为统一选项，使所有功能（LLM、图像生成、视频生成、Embedding）都支持通过阿里云百炼平台的 OpenAI 兼容接口调用千问模型，同时保留原有模型提供商支持。

## 阿里百炼平台 API 分析

### 端点配置
- **OpenAI 兼容端点**: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- **DashScope 端点**: `https://dashscope.aliyuncs.com/api/v1`
- **用户自定义端点**: `https://llm-zdkaid591zmx8w2t.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`

### 支持的模型

| 模型类型 | 模型名称 | 说明 |
|----------|----------|------|
| **LLM 文本模型** | qwen-turbo | 高性价比，适合简单任务 |
| | qwen-plus | 平衡性能与成本 |
| | qwen-max | 最强性能 |
| **Embedding 向量模型** | text-embedding-v3 | 1024维（默认），支持多维度 |
| | text-embedding-v4 | Qwen3-Embedding 系列，最高2048维 |
| **图像生成模型** | wanx-v1 | 通义万象文生图 |
| | wanx2.1-t2i-turbo | 图像生成 V2 |
| **视频生成模型** | kling-v1 | 可灵视频生成 |

### LangChain 对接方式

```python
from langchain_openai import ChatOpenAI

# 使用 OpenAI 兼容接口
llm = ChatOpenAI(
    model="qwen-plus",
    api_key="sk-xxx",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)
```

### Embedding API 调用

```python
# OpenAI 兼容方式
import requests

response = requests.post(
    "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "text-embedding-v3",
        "input": "文本内容",
        "dimensions": 1024  # 可选
    }
)
```

## What Changes
- 新增千问 API 配置项（不影响原有配置）
- 新增千问 LLM 客户端选项
- 新增千问图像生成支持
- 新增千问 Embedding 支持
- 更新 .env 配置模板

## Impact
- Affected specs: 所有使用 LLM、图像、视频生成的 Agent
- Affected code: 
  - `src/config/settings.py` - 新增配置项
  - `src/clients/` - 新增千问客户端
  - `src/rag/embeddings.py` - 新增千问 Embedding 支持
  - `src/agents/base.py` - 支持选择千问模型
  - `.env` - 新增配置

## ADDED Requirements

### Requirement: 千问 API 配置
系统 SHALL 支持配置千问系列模型的 API 端点和密钥。

#### Scenario: 配置千问 API
- **WHEN** 用户配置 `QWEN_API_KEY`、`QWEN_API_BASE`
- **THEN** 系统可以使用千问系列模型

### Requirement: 千问 LLM 支持
系统 SHALL 支持通过 OpenAI 兼容接口调用千问 LLM 模型。

#### Scenario: 使用千问 LLM
- **WHEN** 配置 `LLM_PROVIDER=qwen` 且 `LLM_MODEL=qwen-plus`
- **THEN** Agent 使用千问 LLM 进行推理
- **AND** 使用 LangChain ChatOpenAI 客户端
- **AND** base_url 配置为 OpenAI 兼容端点

### Requirement: 千问 Embedding 支持
系统 SHALL 支持通过 OpenAI 兼容接口调用千问 Embedding 模型。

#### Scenario: 使用千问 Embedding
- **WHEN** 配置 `EMBEDDING_PROVIDER=qwen`
- **THEN** 系统使用 `text-embedding-v3` 模型进行向量化
- **AND** 向量维度为 1024（默认）

### Requirement: 千问图像生成支持
系统 SHALL 支持通过 DashScope API 调用千问图像生成模型。

#### Scenario: 使用千问图像生成
- **WHEN** 配置 `IMAGE_PROVIDER=qwen`
- **THEN** 系统使用 `wanx-v1` 模型生成图片

## MODIFIED Requirements

### Requirement: 配置管理
在 `src/config/settings.py` 新增以下配置项：
- `llm_provider`: LLM 提供商选择（dashscope/qwen）
- `embedding_provider`: Embedding 提供商选择（local/qwen）
- `qwen_api_key`: 千问 API Key
- `qwen_api_base`: OpenAI 兼容端点（默认阿里云官方端点）