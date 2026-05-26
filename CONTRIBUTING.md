# 贡献指南

感谢你对 Agent Part 项目的关注！我们欢迎各种形式的贡献。

## 如何贡献

### 报告 Bug

使用 [Bug Report](https://github.com/JianFeiGan/agent_part/issues/new?template=bug_report.md) 模板提交 Issue。

### 提交功能请求

使用 [Feature Request](https://github.com/JianFeiGan/agent_part/issues/new?template=feature_request.md) 模板提交 Issue。

### 提交代码

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的改动 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 开发环境

```bash
# 克隆仓库
git clone https://github.com/JianFeiGan/agent_part.git
cd agent_part

# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env

# 运行测试
uv run pytest

# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check .
```

## 代码规范

- 遵循 PEP 8，使用 `ruff format` 格式化
- 所有公共函数必须有类型注解
- 使用 Google 风格 docstring
- 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范

## 提交信息格式

```
<type>(<scope>): <subject>

<body>

<footer>
```

类型：
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建/工具相关

## Pull Request 规范

- PR 标题简洁明了
- 描述中说明改动的原因和内容
- 确保所有测试通过
- 确保代码格式符合规范
- 关联相关的 Issue

## 行为准则

- 尊重他人，保持友善
- 建设性地讨论问题
- 欢迎新手提问
