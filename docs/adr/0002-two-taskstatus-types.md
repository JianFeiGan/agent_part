# 生成任务与刊登任务的状态类型保持分离

「生成任务」与「刊登任务」的状态类型在代码中**都叫 `TaskStatus`**，但它们描述两套不同的状态机，我们**刻意不合并**，也**不共用状态映射函数**。

**Status**: accepted

## 背景

- 生成任务（`src/types/task.ts`）：`TaskStatus` 是 **enum**，五态 —— pending / running / completed / failed / cancelled
- 刊登任务（`src/types/listing.ts`）：`TaskStatus` 是 **联合类型**，八态 —— 含 pending / generating / reviewing / pushing / completed / failed / published / partial

两者共享 `pending`、`completed`、`failed` 三个状态名，但刊登独有 `generating`、`reviewing`、`pushing`、`published`、`partial`。其中 `partial` 表示「部分平台推送成功」，生成任务没有对应概念。

## Considered Options

1. **保持分离（选此方案）**：两套映射各写各的，代价是有重复代码。
2. **合并为一套**：需要同时改后端两套状态机，牵动任务持久化与推送逻辑；且 `partial` 这类刊登特有终态无处安放。
3. **共用映射函数**：最具迷惑性的选项。把生成任务的映射用在刊登任务上，`published` 和 `partial` 会静默落入兜底样式——**不报错，只是显示错误**，是最难发现的一类 bug。

## Consequences

- 新增状态相关代码前，必须先确认面向哪一套状态机。术语区分见 `CONTEXT.md` 的「⚠️ 同名词：两个 TaskStatus」。
- `src/utils/format.ts` 中的 `getTaskStatusLabel` / `getTaskStatusTagType` **仅适用于生成任务**，不得用于刊登任务视图。
- 刊登任务的两个视图（`listing/TaskList.vue`、`listing/TaskDetail.vue`）各自保留本地 `statusType` 映射，且二者原本就存在细微差异（后者缺 `generating`），本次未做统一——属既有行为，改动需单独评估。
