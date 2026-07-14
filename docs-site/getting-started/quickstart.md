# 5 分钟上手

## 1. 启动服务

```bash
# 配置环境变量（至少需要千问 API Key）
cp .env.example .env
# 编辑 .env，设置 QWEN_API_KEY=your_key

# Docker 一键启动
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
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "name": "智能运动手表",
    "category": "digital",
    "description": "支持心率监测、睡眠追踪的智能手表，1.4 英寸 AMOLED 屏幕"
  }'
```

## 3. 创建视觉生成任务

在管理后台点击「任务管理」→「创建任务」，选择商品并配置：

- **任务类型**：图片 + 视频
- **图片类型**：主图、场景图、卖点图
- **视频时长**：30 秒
- **风格**：专业商业

Agent 工作流将自动执行 7 步流程：

```
编排调度 → 需求分析 → 创意策划 → 视觉设计 → 图片生成 → 视频生成 → 质量审核
```

- 图片由 DashScope 万象 API 生成（wanx-v1 / wan2.7-image-pro）
- 视频由可灵 AI 生成（kling-v1）
- 需求分析、创意策划、质量审核三个 Agent 自动注入 RAG 知识增强

## 4. 查看生成结果

任务详情页展示完整的工作流执行过程：

- **Agent 执行日志**：7 步工作流时间线，含 Token 消耗和费用估算
- **生成图片**：网格预览
- **生成视频**：在线播放
- **质量评分**：自动审核结果与问题检测

## 5. 知识库增强

上传品牌规范、类目知识等文档，RAG 检索会自动为 Agent 提供知识增强：

```bash
# 上传文档
curl -X POST http://localhost:8000/api/v1/knowledge/documents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your-token>" \
  -d '{
    "title": "智能手表品牌规范",
    "doc_type": "brand_guide",
    "category": "digital",
    "content": "品牌调性：科技感、运动活力..."
  }'
```

支持的文档类型：

| 类型 | 说明 | 用途 |
|------|------|------|
| `brand_guide` | 品牌规范 | 品牌调性、视觉规范、语言风格 |
| `category_knowledge` | 类目知识 | 商品特点、卖点模板、关键词 |
| `case_study` | 成功案例 | 历史优秀创意方案参考 |
| `compliance_rule` | 合规规则 | 广告法禁止词、平台审核标准 |

知识库还支持 Graph RAG（知识图谱实体/关系检索）和类目记忆（累积经验），为 Agent 提供更深层的知识增强。

## 6. 多平台刊登

导入商品后，创建刊登任务，自动执行：

```
商品导入 → [素材优化 + 文案生成](并行) → 合规检查 → 推送到 Amazon/eBay/Shopify
```

- **素材优化**：裁剪/压缩/格式转换，适配各平台规格
- **AI 文案生成**：千问 LLM 润色 + 规则草稿降级
- **合规检查**：禁词检测 + 平台规则校验
- **适配器配置**：凭证加密存储（Fernet），支持多店铺

## 7. AI 费用追踪

在「AI 会话」页面查看：

- Token 消耗明细（输入/输出/总计）
- 按模型分解的使用分析
- 按 Agent 分解的使用分析
- 日/月费用预算与估算

## 下一步

- 了解 [系统架构](../concepts/architecture.md)
