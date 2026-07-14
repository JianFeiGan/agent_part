# 安全策略

## 报告漏洞

如果你发现安全漏洞，请**不要**在公开 Issue 中报告。

请发送邮件至 [ganjianfei@users.noreply.github.com]，包含：

1. 漏洞描述
2. 复现步骤
3. 影响范围
4. 建议的修复方案（如有）

我们会在 48 小时内回复，并在修复后发布安全更新。

## 支持的版本

| 版本 | 支持状态 |
|------|----------|
| 0.2.x | ✅ 支持 |

## 安全最佳实践

### API Key 管理

- 所有 API Key（DashScope、千问百炼、可灵AI、OSS 等）均通过 `.env` 环境变量注入，不在代码中硬编码
- `.env` 文件已在 `.gitignore` 中排除，不会被提交到版本控制
- 百炼平台 API Key 统一管理：`dashscope_api_key` 与 `qwen_api_key` 互相回退，避免重复配置
- LangSmith 追踪 API Key 仅在 `langchain_tracing_v2=True` 且 Key 非空时启用
- 占位资产降级开关 `allow_mock_assets` 生产环境必须设为 `False`，防止静默产出假数据

### 凭证加密（EncryptedJSONB）

- 平台适配器凭证使用 `EncryptedJSONB`（基于 `cryptography.fernet.Fernet`）透明加密存储于 PostgreSQL
- 写入时自动加密，格式为 `{"_encrypted": true, "v": 1, "ciphertext": "<Fernet token>"}`
- 读取时自动解密，兼容旧明文数据（无 `_encrypted` 标记时原样返回）
- 加密密钥通过 `CREDENTIALS_ENCRYPTION_KEY` 环境变量配置，未配置时 fail closed（抛出异常）
- API 响应中凭证字段自动脱敏：所有值替换为 `"***"`，绝不返回明文凭证

### Token 认证

- API Token 使用 SHA256 哈希存储，注册表仅保存 `token_hash`，不接受明文 token
- 验证时使用 `secrets.compare_digest` 进行恒定时间比较，防止时序攻击
- 支持 Scope 权限控制：`products:read/write`、`tasks:read/write`、`assets:read/write`，以及通配符 `*`
- 多租户隔离：所有数据操作按 `tenant_id` 过滤，租户间数据不可见
- Token 注册表 JSON 解析失败时 fail closed（返回 503），不泄露内部信息
- WebSocket 连接同样需要鉴权，默认禁止查询参数传递 token（`auth_allow_ws_query_token=False`）

### 通用建议

- 生产环境必须启用 `auth_enabled=True`，关闭开发模式旁路
- CORS 来源通过 `cors_allow_origins` 严格配置，禁止使用通配符
- 定期轮换 `CREDENTIALS_ENCRYPTION_KEY`（轮换后旧密文需重新加密）
- 定期更新依赖以获取安全补丁（`uv sync`）
- 在生产环境中使用 HTTPS，防止传输层泄露
