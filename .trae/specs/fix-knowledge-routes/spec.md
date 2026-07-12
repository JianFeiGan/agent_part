# 修复前端路由缺失视图文件 Spec

## Why

前端路由配置引用了不存在的视图文件 `@/views/knowledge/index.vue` 和 `@/views/knowledge/Search.vue`，导致应用运行时报错，无法正常启动。

## What Changes

- 创建 `frontend/src/views/knowledge/` 目录
- 创建 `frontend/src/views/knowledge/index.vue` - 知识库管理页面
- 创建 `frontend/src/views/knowledge/Search.vue` - 检索测试页面

## Impact

- Affected specs: 前端路由功能
- Affected code: `frontend/src/router/index.ts`, `frontend/src/views/knowledge/`

---

## ADDED Requirements

### Requirement: 知识库管理页面

系统 SHALL 提供知识库管理页面，允许用户：

#### Scenario: 查看知识库列表
- **WHEN** 用户访问 `/knowledge` 路径
- **THEN** 显示知识库文档列表，包含文档名称、类型、创建时间

#### Scenario: 显示占位内容
- **WHEN** 知识库 API 未实现
- **THEN** 显示"功能开发中"占位提示

### Requirement: 检索测试页面

系统 SHALL 提供检索测试页面，允许用户：

#### Scenario: 测试知识检索
- **WHEN** 用户访问 `/knowledge/search` 路径
- **THEN** 显示检索测试界面，包含搜索输入框和结果展示区域

#### Scenario: 显示占位内容
- **WHEN** 检索 API 未实现
- **THEN** 显示"功能开发中"占位提示