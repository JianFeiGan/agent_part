---
feature: frontend-productization
status: in-progress
updated: 2026-09-12
branch: feat/frontend-productization
commits: 694f325..472a793
---

# Frontend Productization（前端产品化四期）

## Report

**What was built**

1. **质量门槛恢复**：`frontend/.npmrc` 固定 `legacy-peer-deps`；`createEmptyAgentLog` 修复 `Detail.vue` 类型崩溃；products/tasks API 解包为业务数据；主链路状态映射收敛到 `utils/format.ts`。
2. **主链路产品化**：`useTaskStatusCoordinator`（WS 优先 + running 断线 5s 轮询 + 终态补拉）；工作台默认概览、Agent 诊断折叠；资产预览/播放/下载；商品/任务列表 `PageState` 三态。
3. **知识库闭环**：管理页对接真实 `/knowledge`（列表/上传/新建/删除/统计），检索页增加文档检索模式。
4. **记忆 HITL**：`/memory-proposals` 审核页（过滤/详情/通过/拒绝/从任务提炼）。

**Verification**

- `cd frontend && npm run typecheck` — PASS
- `npm test` — PASS（14 tests / 4 files）
- `npm run lint` — 0 errors，5 个既有 warning
- `npm run build` — PASS

**Journey log**

- npm `edgesOut` 崩溃来自 vitest@4 + vite@5 peer 解析，用 `.npmrc legacy-peer-deps` 固定即可，不必升级大版本。
- 实际详情路由是 Workbench，不是 `tasks/Detail.vue`（后者是孤儿页）；状态映射仍要单源。
- Search 页原走 graphs 占位 hybrid API；本轮补了真实 `/knowledge/search` 的 docs 模式，hybrid/agent 保留。
- T7 端到端需真实后端+DB 联调，本环境未跑通，**故 status 仍为 in-progress**，保持未勾选。

## [S1] Problem

后端视觉生成 / 刊登 / RAG 能力已经成形，但**运营用户还无法可靠地走完一条产品主路径**：

1. 前端质量门槛是红的：`npm install` 遇 vitest peer 解析需 `--legacy-peer-deps`；`typecheck`/`build` 因 `tasks/Detail.vue` 的 `AgentLog` 类型不完整而失败；`vitest` 仅 1 个 spec（7 用例）。
2. 商品 → 生成任务 → 工作台 → 资产下载链路割裂：入口虽已有「生成任务」按钮与 URL 预选，但工作台默认堆满 Agent 诊断信息；WS 断线无 5s 轮询兜底；**资产无下载动作**；三态/空态不统一。
3. 知识库双轨：真实能力在 `src/rag/*` + `/api/v1/knowledge`，但 `src/knowledge/*` 与 `/api/v1/knowledge/graphs` 仍是占位/内存实现；前端管理页是 empty 占位，上传按钮 disabled。
4. 记忆 HITL 断在前端：`/api/v1/memory-proposals` 审核 API 完整，前端无任何审核 UI。

对应已有工作：GitHub Issue #10 Spec + #11–#17（T1–T7，主链路）；知识库与记忆为本轮新增范围。

## [S2] Design

### 总原则

- 单分支 `feat/frontend-productization`，**四期串行**，每期可独立验收。
- 主链路验收标准以 GitHub **#10 / #11–#17** 为源；本文件不复制全部 user story，只记录本轮对齐后的契约与增量决策。
- 后端只在主链路展示急需字段时补；**不扩大到全站重构**。
- 生成任务状态映射只维护 `frontend/src/utils/format.ts` 一处；刊登任务不得复用（见 ADR-0002）。

### Phase 1 — 质量门槛（覆盖 #11 T1）

**目标**：`typecheck` / `test` / `build` 全绿，后续改造有安全网。

| 契约 | 决策 |
|---|---|
| npm 安装 | 在 `frontend/package.json` 或 README 记录 `npm install --legacy-peer-deps`；根因是 vitest@4 与 vite@5 的 peer 解析触发 npm arborist `edgesOut` 崩溃。不升级 vite/vitest 大版本（范围外） |
| `AgentLog` 兜底 | `Detail.vue` 合成默认日志时必须补齐 `AgentLog` 全字段（`input_data`/`output_data`/`prompt_*`/`tokens`/`cost_cny`/`latency_ms`/`model_name`/`provider`/`child_calls`）；空值用 `null`/`0`/`[]`。可抽 `createEmptyAgentLog()` 到 `types/task.ts` 或 `utils/` |
| API 解包 | 主链路 API（products/tasks/assets）页面层拿到业务数据，不再各自 `response.data.data`；失败仍由 axios 拦截器全局提示，业务层不二次弹错（ADR-0001） |
| 状态映射 | 生成任务标签/tag 类型只出自 `getTaskStatusLabel` / `getTaskStatusTagType` |
| 最小测试 | 补：状态映射、AgentLog 兜底构造、主链路 API 解包；允许引入测试所需最小依赖 |
| 401 | 跳转首页并提示需登录；**不做**完整登录页 |

### Phase 2 — 主链路 UX（覆盖 #12–#17 / T2–T7）

**目标**：运营可从商品列表顺畅走到「看到并下载资产」。

已具备（不重做）：

- 商品列表行内「生成任务」入口 → `tasks/create?product_id=...`
- 任务创建页读取 `route.query.product_id` 预选

待做：

| 区域 | 行为契约 |
|---|---|
| 商品入口 | 补商品搜索下拉（创建页）；空态引导「创建商品」；提交中禁用按钮；失败保留表单 |
| 实时协调层 | 新建 composable（如 `useTaskStatusCoordinator`）：WS 优先；断线/不可用且 `running` 时 **5s** 轮询轻量状态；终态停止轮询并补拉完整详情；页面只消费 status/progress/connection，不直接协调 WS/轮询 |
| 三态 | 共享 `PageState`（loading/empty/error）组件；商品/任务列表与工作台共用；error 提供重试，不重复弹错 |
| 工作台信息架构 | **默认概览优先**：状态、进度、当前阶段、关键错误、结果概要；Agent DAG/IO/日志/指标默认折叠，可展开诊断 |
| 资产 | 工作台内图片预览、视频播放；**每个资产提供下载**；无资产明确空态；URL 失效有兜底；不新增独立资产页 |

### Phase 3 — 知识库管理闭环

**目标**：运营可上传/管理知识文档；检索页与管理页一致走真实 `/knowledge` API。

| 契约 | 决策 |
|---|---|
| 后端 | **以 `/api/v1/knowledge`（`knowledge.py`）为唯一真实实现**。`knowledge_graph.py` 的内存 `_graphs` 与 `src/knowledge/*` 占位：路由上标记 deprecated 或改为代理到真实实现；不在本轮重写图谱引擎 |
| 前端管理页 | 替换 empty 占位：文档列表（分页）、创建/上传、删除、统计；上传按钮可用 |
| 与 Search 页 | Search 继续用 `/knowledge/search`；管理页与 Search 共享 types/API 封装 |
| 三态 | 复用 Phase 2 的 PageState |
| 不在本轮 | GraphRAG 图谱可视化、HyDE 配置 UI、评估报表页 |

### Phase 4 — 记忆审核前端

**目标**：点亮 HITL——人能审 `category_memory_proposals`。

| 契约 | 决策 |
|---|---|
| 页面 | 新路由 `/memory-proposals`（或挂在知识库下二级页）：提案列表（状态/类目过滤、分页）、详情（best_practices / negative_patterns / style_guidelines 等）、通过（可覆盖字段）、拒绝（必填理由） |
| API | 对接既有 `/api/v1/memory-proposals/*`；新增 `frontend/src/api/memoryProposals.ts` + types |
| 触发 | 提供「从任务提炼」入口（`POST /distill`，`source_type=task_completion`）；**不做**定时自动提炼 |
| 权限 | 仅 `memory:write` 可审批；无权限时只读隐藏操作按钮 |

### 跨期约定

- 浅色主题为主；工作台诊断区可保留深色工作区（#10 已定）。
- `lint` 警告数量不增加。
- 孤儿页面只做类型/构建修复，不扩功能。

## [S3] Out of Scope

- 全站视觉重构、暗色主题切换
- 登录页 / OAuth / 用户体系
- 评估报表页面、工作流可视化编辑器（v0.4.0）
- 真实 Amazon/eBay/Shopify 生产联调
- 升级 vite 6 / vitest 大版本、迁移包管理器
- 重写 `src/rag` GraphRAG 引擎或删除全部历史占位模块（只做接口收敛）

## Tasks

- [x] T1: 修复前端质量门槛（install 说明、AgentLog 类型、typecheck/test/build 全绿、主链路 API 解包与状态映射测试）— acceptance: `npm run typecheck && npm test && npm run build` 通过；`--legacy-peer-deps` 有文档；状态映射与空 AgentLog 有测试 (covers: S2 Phase1)
- [x] T2: 商品→任务创建入口与提交体验 — acceptance: 从商品列表进入创建页并预选；可搜索商品；空态引导；提交中禁用；失败保留输入；关键行为有测试 (covers: S2 Phase2; depends: T1; refs: #12)
- [x] T3: 任务实时状态协调器 — acceptance: WS 优先；running 且断线时 5s 轮询轻量状态；终态停轮询并补拉详情；页面可感知连接状态；协调逻辑有测试 (covers: S2 Phase2; depends: T1; refs: #13)
- [x] T4: 主链路三态与空态组件 — acceptance: 商品/任务列表与工作台共用 PageState；空态有下一步；error 有重试且不重复弹错；有测试 (covers: S2 Phase2; depends: T3; refs: #14)
- [x] T5: 工作台概览优先信息架构 — acceptance: 默认见概览（状态/进度/阶段/错误/结果）；Agent 明细默认折叠可展开；1280px+ 布局清晰；有测试 (covers: S2 Phase2; depends: T4; refs: #15)
- [x] T6: 工作台资产展示与下载 — acceptance: 图片预览、视频播放、每资产可下载、空态/坏 URL 兜底；不新增独立资产页；有测试 (covers: S2 Phase2; depends: T5; refs: #16)
- [ ] T7: 主链路端到端验收 — acceptance: 商品→任务→工作台→资产可走通；WS 与轮询路径可验证；三终态展示正确；typecheck/test/build/lint 达标 (covers: S2 Phase2; depends: T2,T5,T6; refs: #17)
- [x] T8: 知识库管理页闭环 — acceptance: 列表/上传/删除/统计可用；走真实 `/knowledge` API；占位知识图谱路由不再作为前端数据源；三态达标；有关键路径测试 (covers: S2 Phase3; depends: T4)
- [x] T9: 记忆提案审核 UI — acceptance: 列表/过滤/详情/approve/reject 可用；拒绝必填理由；可从任务触发 distill；无 write 权限隐藏操作；有测试 (covers: S2 Phase4; depends: T4)
- [x] T10: 四期收口与文档对齐 — acceptance: README/CLAUDE.md 中与本轮相关的质量门槛与页面说明已更新；本 spec Report 填写交付摘要与验证命令 (covers: S1,S2; depends: T7,T8,T9)
