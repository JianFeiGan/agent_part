# 5 分钟上手

## 1. 启动服务

```bash
docker compose up -d
```

访问 http://localhost:3000 打开管理后台。

## 2. 创建商品

在管理后台点击「商品管理」→「创建商品」，填写商品信息：

- **名称**：智能运动手表
- **类目**：digital
- **描述**：支持心率监测、睡眠追踪的智能手表，1.4 英寸 AMOLED 屏幕

或通过 API：

```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "name": "智能运动手表",
    "category": "digital",
    "description": "支持心率监测、睡眠追踪的智能手表，1.4 英寸 AMOLED 屏幕"
  }'
```

## 3. 创建视觉生成任务

在管理后台点击「任务管理」→「创建任务」，选择商品并配置：

- **任务类型**：图片 + 视频
- **图片类型**：主图、场景图
- **视频时长**：5 秒
- **风格**：专业商业

Agent 工作流将自动执行：需求分析 → 创意策划 → 视觉设计 → 图片/视频生成 → 质量审核

## 4. 查看生成结果

任务详情页展示完整的工作流执行过程：

- **Agent 执行日志**：6 步工作流时间线
- **生成图片**：网格预览
- **生成视频**：在线播放
- **质量评分**：自动审核结果

## 5. 更多功能

### 知识库增强

上传品牌规范、类目知识等文档，RAG 检索会自动为 Agent 提供知识增强：

```bash
# 上传文档
curl -X POST http://localhost:8000/api/v1/knowledge/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "智能手表品牌规范",
    "doc_type": "brand_guide",
    "category": "digital",
    "content": "品牌调性：科技感、运动活力..."
  }'
```

### 多平台刊登

导入商品后，创建刊登任务，自动执行素材优化 → 文案生成 → 合规检查 → 推送到 Amazon/eBay/Shopify。

### AI 费用追踪

在「AI 会话」页面查看 Token 消耗、按模型/Agent 分解的使用分析、日/月费用预算。

## 下一步

- 了解 [系统架构](../concepts/architecture.md)
