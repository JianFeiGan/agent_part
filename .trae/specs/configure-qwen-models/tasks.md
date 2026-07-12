# Tasks

- [x] Task 1: 更新配置文件 settings.py
  - [x] SubTask 1.1: 新增提供商选择配置项（llm_provider, image_provider, embedding_provider）
  - [x] SubTask 1.2: 新增千问 API 配置项（qwen_api_key, qwen_api_base, qwen_dashscope_base）
  - [x] SubTask 1.3: 新增千问模型名称配置项

- [x] Task 2: 更新 .env 配置
  - [x] SubTask 2.1: 更新 .env.example 模板添加千问配置
  - [x] SubTask 2.2: 使用用户提供的 API Key 和端点配置 .env

- [x] Task 3: 新增千问 LLM 客户端
  - [x] SubTask 3.1: 创建 `src/clients/qwen_llm_client.py`
  - [x] SubTask 3.2: 实现 OpenAI 兼容接口调用
  - [x] SubTask 3.3: 更新 `src/agents/base.py` 支持提供商选择

- [x] Task 4: 更新图像生成客户端
  - [x] SubTask 4.1: 在 `src/clients/dashscope_image_client.py` 添加千问端点支持
  - [x] SubTask 4.2: 更新 provider_result.py 添加千问检测

- [x] Task 5: 新增千问 Embedding 客户端
  - [x] SubTask 5.1: 创建 `src/clients/qwen_embedding_client.py`
  - [x] SubTask 5.2: 更新 `src/rag/embeddings.py` 支持提供商选择

- [x] Task 6: 更新知识库模块
  - [x] SubTask 6.1: 更新 `src/knowledge/graph_builder.py` 支持千问 LLM
  - [x] SubTask 6.2: 更新 `src/knowledge/agent_workflow.py` 支持千问 LLM
  - [x] SubTask 6.3: 更新 `src/knowledge/document_ingestion.py` 支持千问 Embedding

- [x] Task 7: 验证配置
  - [x] SubTask 7.1: 测试千问 LLM 调用
  - [x] SubTask 7.2: 测试千问图像生成
  - [x] SubTask 7.3: 测试千问 Embedding
  - [x] SubTask 7.4: 重新构建 Docker 并验证所有功能

# Task Dependencies
- Task 2 depends on Task 1
- Task 3, 4, 5, 6 depend on Task 2
- Task 7 depends on Task 3, 4, 5, 6