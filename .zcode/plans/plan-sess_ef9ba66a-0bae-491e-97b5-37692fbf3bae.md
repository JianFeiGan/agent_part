# 按严重度分级的全量修复方案（P0–P3）

基于已核实的代码（修正初扫两处误报：图片实际经 `AssetPersister` 落库、`thread_id` 实际用 task_id；确认新问题：**视频完全无落库路径**）。按 P0→P3 顺序实施，每阶段跑 `uv run pytest` 验证。

## P0 数据正确性 / 生产安全

**1. 任务取消语义 + 进度保留**
- `src/api/schema/task.py:27`：`TaskStatus` 增加 `CANCELLED = "cancelled"`
- `src/api/service/task_manager.py`：`cancel_task`（:431-434）与 `CancelledError` 分支（:280-288）改写 CANCELLED；失败/取消分支不再把 progress 置 0（保留 Redis 中当前进度）
- 前端：`frontend/src` 任务相关 view/status 映射与 TS 类型增加 cancelled（灰色标签）
- 更新/新增对应测试

**2. 视频产物落库缺失**
- `src/api/service/asset_persister.py`：新增 `persist_videos()`（镜像 `persist_images`，asset_type="video"，is_mock 按模型判断）
- `src/api/service/task_manager.py:243-260`：落库分支追加视频持久化
- 新增测试

**3. completed_steps 永远为空**
- `src/graph/workflow.py` 7 个节点成功分支：`"completed_steps": [*state.completed_steps, "<step_name>"]`（LangGraph 节点返回值才生效；Agent 内 `mark_step_completed` 原地调用对直接单测仍有意义，保留）
- 测试断言跑完工作流后 completed_steps 非空且有序

**4. Mock 假资产默认关闭（fail-closed）**
- `src/config/settings.py:179`：`allow_mock_assets` 默认改 False
- `.env.example`：加 `ALLOW_MOCK_ASSETS=true` 注释说明（本地无 Key 开发用）
- `tests/conftest.py`：显式设 `ALLOW_MOCK_ASSETS=true` 保持 CI 占位路径行为；逐个排查依赖该默认值的测试
- `task_manager.get_task_detail`：响应增加 `has_mock_assets` 透传（images metadata 已含 is_mock）

## P1 鲁棒性

**5. LLM 调用重试**
- `src/agents/base.py:256 invoke_llm`：用 tenacity（已是依赖）异步重试包裹 `chain.ainvoke`，仅重试瞬态异常，重试次数/退避从 settings 读（新增 `llm_retry_attempts=2`、`llm_retry_initial_backoff=1.0`），每次重试记 warning

**6. 统一 JSON 提取**
- 新建 `src/agents/llm_json.py`：`extract_json(text) -> dict | None`，处理 ```json 围栏、花括号配对、strip；解析失败 logger.warning
- 替换 orchestrator / requirement_analyzer / creative_planner / visual_designer / quality_reviewer 中约 6 处手工 `find("{")/rfind("}")`；兜底默认值逻辑不变，但从"静默"变"有日志"
- 新增 `tests/test_agents/test_llm_json.py` 单测

**7. 质量审核 fail 策略统一**
- `src/agents/quality_reviewer.py:213/380`：JSON 解析失败走与异常一致的 fail-closed 路径（0 分 + high 级 issue"审核结果解析失败"），消除与注释的矛盾

**8. tenant_id 显式传递**
- `src/graph/state.py`：`GenerationRequest` 与 `AgentState` 增加 `tenant_id: str = "system"`；`create_initial_state` 加参数
- `task_manager.create_task/_execute_workflow` 传入 tenant_id
- `image_generator._resolve_tenant_id` / video 同款：优先读 state 字段（getattr 链保留一版兼容）
- `WorkflowBuilder`/`ProductVisualWorkflow` 增加可选 `tenant_id`/`task_id`，创建 Agent 时传给 BaseAgent 构造器（BaseAgent 已支持，目前从未传入 → 顺带修好会话记录租户隔离）

**9. astream 性能**
- `task_manager.py:217-238`：改用 `stream_mode="values"` 直接取每步完整 state，删除循环内 `aget_state` 双倍 checkpoint 往返；最终状态取最后一个 value

## P2 架构卫生

**10. 消除双 AgentState 重名**
- `src/agents/base.py:53` 的 `AgentState` 重命名为 `AgentRuntimeState`，更新所有 agents 文件及测试的 import；清理 `src/agents/__init__.py` 的 `BaseAgentState` 别名

**11. 死代码清理**
- 删除：`base.py` 伪实现 `retrieve_knowledge`、`RunnableAgent`、无人消费的 `register_tool/_tools`、`AgentResult.next_agent` 字段及各 Agent 的赋值、`image_generator.py` 的 `ImageGenerationInput`/`_create_asset_po`/`_call_image_api` 的 session 参数（落库统一归 AssetPersister，消除双写隐患）、`orchestrator.summarize_results`
- 同步更新引用它们的测试（如 test_mock_providers 中显式传 session 断言 PO 的用例改为断言 AssetPersister 行为）

**12. workflow 节点样板抽象**
- `workflow.py:322-497`：抽通用 `make_agent_node(agent_key, agent, result_mapper)` 工厂，7 个闭包收敛为一个

**13. 视频时长字段一致性**
- `video_generator.py`：真实路径裁剪为 10s 后，`GeneratedVideo.duration`/metadata 统一用裁剪值；mock 假 MP4 的 metadata 保持明确 note

## P3 基础设施

**14. 引入 Alembic**
- `uv add alembic`；`alembic init migrations`；env.py 接 async engine + settings；生成与当前 `src/db/models.py`/`listing_models.py`/`conversation_models.py` 一致的基线迁移
- `postgres.py:141` 的 `create_all` 保留但挂在 settings 开关后（`db_auto_create`，默认 True 便于开发），README/AGENTS.md 注明生产用迁移 + 对已存在库 `alembic stamp head`

**15. WebSocket 广播改 Redis pub/sub + 僵尸任务回收**
- `_broadcast_event` 改为发布 Redis 频道 `task_events:{tenant_id}:{task_id}`；WS 端点改为订阅该频道转发（替换进程内 `_ws_subscribers` 字典），多 worker 下事件不再丢
- 启动时（main.py lifespan）扫描 Redis 中 status=RUNNING 但进程内无对应 asyncio.Task 的记录，标记 FAILED（"服务重启导致中断"），消除永久卡死的 RUNNING 任务

**16. Embedding 维度配置化**
- settings 增加 `embedding_dimension=1024`；`src/db/models.py` 4 处 `Vector(1024)` 与 `vector_store.py` 的 CAST 改读 settings；文档注明改维度需配合迁移

## 验证与收尾
- 每阶段：`uv run pytest`（634 个测试全绿）；P0 完成后手动起服务验证取消/失败任务进度不回跳（可选）
- 最终同步更新 AGENTS.md（TaskStatus 增 cancelled、ALLOW_MOCK_ASSETS 说明、Alembic 用法）
- 不做 git 提交（未要求）；工作区已有 7 个测试文件未提交改动，实施时在其之上继续修改