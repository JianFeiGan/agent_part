# 主分支代码评审 Spec

## Why

项目已完成初始开发，需要拉取主分支最新代码并进行系统性代码评审，识别潜在问题、改进空间和最佳实践符合度。

## What Changes

- 拉取远程 master 分支最新代码
- 对核心模块进行系统性代码评审
- 生成评审报告，包含问题和建议

## Impact

- Affected specs: 代码质量保证
- Affected code: 全项目核心模块

---

## ADDED Requirements

### Requirement: 代码评审流程

系统 SHALL 执行以下代码评审步骤：

#### Scenario: 拉取最新代码
- **WHEN** 执行 `git pull origin master`
- **THEN** 本地代码与远程主分支同步

#### Scenario: 后端代码评审
- **WHEN** 审查 `src/` 目录下的核心模块
- **THEN** 识别以下问题类型：
  - 类型注解缺失或不完整
  - 错误处理不当
  - 安全隐患（敏感信息泄露）
  - 代码风格不符合 PEP 8
  - 缺少必要的测试覆盖

#### Scenario: 前端代码评审
- **WHEN** 审查 `frontend/src/` 目录
- **THEN** 识别以下问题类型：
  - TypeScript 类型定义问题
  - Vue 组件最佳实践符合度
  - API 调用安全性

#### Scenario: 评审报告输出
- **WHEN** 完成所有模块评审
- **THEN** 输出评审报告至 `.trae/specs/code-review/report.md`，包含：
  - 问题清单（按严重程度分级）
  - 改进建议
  - 最佳实践符合度评估