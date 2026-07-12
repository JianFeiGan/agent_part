# 代码评审检查清单

## 前置条件
- [x] 已拉取 master 分支最新代码，无冲突
- [x] 已确认最新提交记录

## 后端代码评审
- [x] `src/agents/` 模块评审完成，类型注解完整
- [x] `src/api/` 模块评审完成，路由和验证符合规范
- [x] `src/db/` 模块评审完成，数据库操作安全
- [x] `src/rag/` 模块评审完成，RAG 实现正确
- [x] `src/graph/` 模块评审完成，状态图设计合理
- [x] `src/clients/` 模块评审完成，外部 API 调用安全

## 前端代码评审
- [x] `frontend/src/api/` 评审完成，API 调用封装合理
- [x] `frontend/src/views/` 评审完成，Vue 组件符合最佳实践
- [x] `frontend/src/types/` 评审完成，TypeScript 类型定义完整

## 安全审查
- [x] 无敏感信息硬编码（API Key、密码等）
- [x] 环境变量处理安全
- [x] 配置类实现安全

## 评审报告
- [x] 评审报告已输出至 `.trae/specs/code-review/report.md`
- [x] 问题按严重程度分级（Critical/High/Medium/Low）
- [x] 包含改进建议和最佳实践评估