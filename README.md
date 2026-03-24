# 多Agent协作商品图片/视频自动生成系统

基于 LangGraph 构建的多Agent协作系统，实现商品营销视觉内容的自动化生成。

## 功能特性

- 🤖 **多Agent协作架构**: 7个专业Agent协同工作
- 🖼️ **智能图片生成**: 主图、场景图、卖点图自动生成
- 🎬 **视频分镜生成**: 智能分镜设计+视频合成
- 🎨 **创意自动策划**: 风格推荐、配色方案设计
- ✅ **质量自动审核**: 内容质量检测、合规审核

## 快速开始

### 安装依赖

```bash
# 使用 uv 安装依赖
uv sync

# 或使用 pip
pip install -e ".[dev]"
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入 API Key
```

### 运行示例

```python
from src.graph import ProductVisualWorkflow, create_initial_state
from src.models import Product, ProductCategory

# 创建商品信息
product = Product(
    name="智能运动手表",
    category=ProductCategory.DIGITAL,
    description="支持心率监测、睡眠追踪的智能手表",
)

# 运行工作流
workflow = ProductVisualWorkflow()
result = await workflow.run(product)
```

## Agent 架构

```
OrchestratorAgent (编排调度)
    ├── RequirementAnalyzerAgent (需求分析)
    ├── CreativePlannerAgent (创意策划)
    ├── VisualDesignerAgent (视觉设计)
    ├── ImageGeneratorAgent (图片生成)
    ├── VideoGeneratorAgent (视频生成)
    └── QualityReviewerAgent (质量审核)
```

## 技术栈

- **Python**: 3.11+
- **LangChain**: LLM 框架
- **LangGraph**: 多Agent编排
- **通义千问**: 主力 LLM
- **通义万象**: 图像生成
- **可灵AI**: 视频生成

## 项目结构

```
src/
├── agents/          # Agent 实现
├── graph/           # 状态图定义
├── models/          # 数据模型
├── tools/           # 工具集成
├── api/             # API 接口
└── config/          # 配置管理

tests/               # 测试用例
documents/           # 开发文档
```

## 开发

```bash
# 运行测试
uv run pytest

# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check .

# 类型检查
uv run mypy src/
```

## License

MIT