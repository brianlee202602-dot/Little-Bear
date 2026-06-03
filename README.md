# Little Bear

更新时间：2026-06-03

Little Bear 是面向企业内部知识检索与问答场景的 RAG 系统工作区。项目目标是让用户只能检索自己有权限访问的知识库和文档，并在文档导入、索引发布、权限变化、模型服务波动和复杂查询场景下保持可审计、可降级、可恢复。

根目录 README 仅作为项目总览入口。部署运行、接口、架构、契约和开发约束请阅读 `docs/` 下的成熟文档。

## 项目结构

```text
apps/api        FastAPI API 服务
apps/worker     文档导入与索引 Worker
apps/web        普通用户查询前端
apps/admin      管理后台前端
packages/       共享契约、前端 SDK 和共享 UI 包
docs/           当前成熟项目文档
tests/          单元、集成、契约和回归测试
```

## 已实现功能

### 平台基础能力

- 系统初始化、setup JWT、企业 / 部门 / 管理员 / 内置角色初始化。
- active config 配置版本管理、配置编辑、激活、归档和配置审计。
- Secret Store 加密保存 MinIO、JWT、模型 provider 等密钥。
- ServiceBootstrap 启动门禁和 live / ready 健康检查。
- 当前 schema 基线迁移。

### 认证、组织与权限

- 本地账号密码登录、JWT access / refresh token、当前用户信息和用户自助改密。
- 用户管理、部门管理、角色绑定和管理后台能力菜单。
- 系统管理员、审计管理员、安全管理员、部门管理员、知识库管理员和普通员工角色边界。
- RBAC scope、部门作用域、知识库作用域、知识库可见性和文档可见性控制。
- Permission Service、access block、权限收紧、文档删除和 fail-closed 权限安全边界。

### 知识库、文档与导入索引

- 知识库列表、新增、编辑、删除、权限设置和运维管理。
- 文件夹管理、文档上传、文档列表、文档详情、文档版本、索引版本和 chunk 预览。
- 文档权限设置、文档来源预览、citation 来源读取、指定文档或批量文档重建索引。
- 导入任务队列、Worker claim、锁接管、失败重试和任务恢复。
- Markdown、TXT、DOCX、PDF 解析，结构化切块，页码、标题路径和 source offsets 元数据写入。
- MinIO 对象存储、embedding 分批处理、Qdrant draft vector 写入、关键词索引账本和 active index 发布。
- 权限变化后的索引 payload 刷新任务。

### RAG 查询链路

- 非流式查询和 SSE 流式查询，支持 provider token 级流式输出。
- 服务端全权限知识库自动搜索。
- Query Rewrite、联合问题拆分、多 query 召回、关键词召回、向量召回、Weighted RRF 融合和 rerank。
- 候选质量 gate、embedding MMR 去冗余、相邻 chunk 扩展和 Context Builder token 预算控制。
- 完整 chunk 正文对象存储回源读取、LLM 回答生成、citation 校验、citation 自动修复和 unauthorized 拦截。
- 检索、rerank、LLM、citation 等阶段的结构化降级。
- query log、model call log、检索诊断和高风险 query audit。

### 普通用户查询前端

- 登录、token refresh、当前用户可访问知识库加载和知识库选择。
- ChatGPT 风格查询工作区、流式 / 非流式查询、多轮会话展示、服务端历史会话同步和会话删除。
- 引用来源、降级状态、置信度展示。
- 查询输入框固定在浏览器底部，刷新和切换会话后的消息顺序已修复。

### 管理后台前端

- 初始化、登录、配置管理、部门管理、用户管理、角色绑定、知识库管理、文件夹管理和文档导入。
- 文档管理弹窗、文档权限设置、文档版本、索引版本、chunk 预览和重建索引。
- 索引运维、Qdrant 快照入口、查询日志、查询检索诊断、模型调用日志和配置审计日志。
- 列表页已按后端分页、筛选和权限过滤展示。

### 诊断、审计与验收

- 审计日志、查询日志、模型调用日志、查询检索诊断、配置审计和索引健康检查。
- P0 smoke、查询回归、RAG 增强回归、Qdrant / embedding 真实联调测试。
- 后端单元测试、前端 typecheck / build 门禁。

## 当前边界

- Redis 已作为基础设施和 ServiceBootstrap 依赖接入，但业务缓存能力尚未实现。
- 当前迁移已压缩为当前 schema 基线，停留在早期增量迁移链中间版本的数据库需要先升到 head 或重建。
- 当前部署说明以本地和内部开发环境为主，尚未提供 Kubernetes / Helm 生产编排。
- 查询多轮会话已保存和展示，但尚未实现长历史总结或跨轮意图规划。
- 最终答案缓存尚未接入。

## 文档入口

总索引：

- [docs/README.md](docs/README.md)

根目录工程入口：

- [AGENTS.md](AGENTS.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [WORKFLOW.md](WORKFLOW.md)

部署与运行：

- [本地开发环境说明](docs/development/本地开发环境说明.md)
- [部署与运行手册](docs/operations/部署与运行手册.md)
- [生产部署拓扑说明](docs/operations/生产部署拓扑说明.md)
- [备份与恢复说明](docs/operations/备份与恢复说明.md)
- [配置变更操作手册](docs/operations/配置变更操作手册.md)

后端：

- [项目总体架构设计书](docs/architecture/项目总体架构设计书.md)
- [核心业务链路时序图](docs/architecture/核心业务链路时序图.md)
- [后端架构设计书](docs/backend/后端架构设计书.md)
- [后端接口文档](docs/backend/后端接口文档.md)
- [后端模块职责索引](docs/backend/后端模块职责索引.md)
- [领域模型与数据关系说明](docs/backend/领域模型与数据关系说明.md)
- [权限模型设计书](docs/backend/权限模型设计书.md)
- [安全边界与威胁模型](docs/backend/安全边界与威胁模型.md)
- [RAG 查询链路实现说明](docs/backend/RAG查询链路实现说明.md)
- [导入与索引生命周期说明](docs/backend/导入与索引生命周期说明.md)
- [模型 Provider 接入说明](docs/backend/模型Provider接入说明.md)
- [配置与 Secret 运行时说明](docs/backend/配置与Secret运行时说明.md)
- [降级策略与错误码说明](docs/backend/降级策略与错误码说明.md)
- [可观测性与诊断说明](docs/backend/可观测性与诊断说明.md)
- [数据库迁移与版本管理说明](docs/backend/数据库迁移与版本管理说明.md)
- [缓存设计说明](docs/backend/缓存设计说明.md)
- [既有文档元数据补齐策略](docs/backend/既有文档元数据补齐策略.md)

前端：

- [管理后台前端架构设计书](docs/frontend/管理后台前端架构设计书.md)
- [管理后台功能与交互说明](docs/frontend/管理后台功能与交互说明.md)
- [查询前端架构设计书](docs/frontend/查询前端架构设计书.md)
- [前后端交互约束说明](docs/frontend/前后端交互约束说明.md)

工程契约：

- [工程契约索引](docs/contracts/README.md)
- [OpenAPI 契约](docs/contracts/openapi.yaml)
- [配置 Schema](docs/contracts/config.schema.json)
- [配置 Schema 说明](docs/contracts/config-schema.md)
- [数据库 Schema](docs/contracts/database-schema.md)
- [权限矩阵](docs/contracts/权限矩阵.md)
- [状态机设计](docs/contracts/状态机设计.md)
- [审计事件字典](docs/contracts/审计事件字典.md)

回归样例：

- [P0 查询回归样例](docs/examples/query-regression.p0.jsonl)
- [RAG 增强查询回归样例](docs/examples/query-regression.rag-enhancement.jsonl)
- [本地初始化样例](docs/examples/setup-initialization.local.p0.json)

测试与验收：

- [测试与验收策略](docs/testing/测试与验收策略.md)
- [模型与检索评测基线](docs/testing/模型与检索评测基线.md)
