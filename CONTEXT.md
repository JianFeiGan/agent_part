# CONTEXT

本文件是术语表，只解释「我们说的词是什么意思」。不含实现细节、不含代码约定。

## 生成任务（Generation Task）

用户提交一个商品 + 一组生成要求后，系统跑的一条工作流。产出图片和/或视频。

**状态机**（`TaskStatus`，五态）：
| 状态 | 含义 |
|---|---|
| `pending` | 已创建，未开始执行 |
| `running` | 工作流执行中 |
| `completed` | 成功完成 |
| `failed` | 失败。进度值保留，不清零 |
| `cancelled` | 被用户取消。进度值保留 |

失败与取消**不清零进度**，避免前端进度条回跳。

## 刊登任务（Listing Task）

把已生成的素材推送到第三方电商平台（Amazon / eBay / Shopify）的一条工作流。

**状态机**（`TaskStatus`，八态）：
`pending` → `generating` → `reviewing` → `pushing` → `completed` / `published` / `partial` / `failed`

其中 `partial` 表示「部分平台推送成功」，是刊登特有的终态。

## ⚠️ 同名词：两个 TaskStatus

「生成任务」与「刊登任务」的状态类型**在代码里都叫 `TaskStatus`**，但它们是**两套不同的状态机**，不可互换：

- 生成任务：`src/types/task.ts` 的 `TaskStatus` **枚举**
- 刊登任务：`src/types/listing.ts` 的 `TaskStatus` **联合类型**

两者**共享 `pending`、`completed`、`failed` 三个状态名**，但刊登还独有 `generating`、`reviewing`、`pushing`、`published`、`partial`。

后果：把生成任务的状态映射函数用在刊登任务上，`published` 和 `partial` 会被静默误判为兜底样式（不报错，只是显示错）。**改状态相关代码前先确认是哪一套。**

## 商品（Product）

被生成素材的主体，含类目、品牌、卖点、规格。

## 资产（Asset）

工作流产出的文件：图片或视频。

## Agent

工作流中的一个执行节点。七个 Agent 按序协作：编排调度 → 需求分析 → 创意策划 → 视觉设计 → 图片生成 / 视频生成 → 质量审核。

## 知识库（Knowledge Base）

供 RAG 检索的企业文档集合，分四类：品牌规范、类目知识、成功案例、合规规则。
