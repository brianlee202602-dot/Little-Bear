# AGENTS.md instructions for Little-Bear

本文件适用于整个仓库。它是自动化编码代理的行为规则入口，不承载完整架构说明和开发流程。架构地图见 [ARCHITECTURE.md](ARCHITECTURE.md)，开发、测试和验收流程见 [WORKFLOW.md](WORKFLOW.md)。

若本文件与更高优先级的系统 / 平台指令冲突，以更高优先级指令为准。

## 1. 代理工作原则

- 回答和面向开发者的说明默认使用中文。
- 修改前先阅读当前任务相关代码、[ARCHITECTURE.md](ARCHITECTURE.md)、[WORKFLOW.md](WORKFLOW.md) 和 `docs/` 下成熟文档。
- 只依据当前代码和 `docs/` 成熟文档判断实现状态；除非用户明确要求，不主动引用历史归档材料。
- 不把未实现能力写成已实现能力。
- 不为了通过当前测试而放宽权限、状态、citation、索引可见性、Secret 或 ServiceBootstrap 边界。
- 不修改与任务无关的文件。
- 不还原用户已有改动。
- 不提交 `.env`、真实密钥、token、密码、完整 prompt、业务文档原文、测试运行产物或敏感 artifacts。

## 2. 必读入口

开始任务时优先阅读：

- [README.md](README.md)：项目简介和文档入口。
- [ARCHITECTURE.md](ARCHITECTURE.md)：系统架构、模块边界和核心链路。
- [WORKFLOW.md](WORKFLOW.md)：开发流程、测试矩阵和验收要求。
- [docs/README.md](docs/README.md)：成熟项目文档索引。

按任务类型追加阅读：

- 后端架构：[docs/backend/后端架构设计书.md](docs/backend/后端架构设计书.md)
- 后端接口：[docs/backend/后端接口文档.md](docs/backend/后端接口文档.md)
- 后端模块：[docs/backend/后端模块职责索引.md](docs/backend/后端模块职责索引.md)
- 安全威胁：[docs/backend/安全边界与威胁模型.md](docs/backend/安全边界与威胁模型.md)
- 权限：[docs/backend/权限模型设计书.md](docs/backend/权限模型设计书.md)
- RAG：[docs/backend/RAG查询链路实现说明.md](docs/backend/RAG查询链路实现说明.md)
- 导入索引：[docs/backend/导入与索引生命周期说明.md](docs/backend/导入与索引生命周期说明.md)
- 模型 Provider：[docs/backend/模型Provider接入说明.md](docs/backend/模型Provider接入说明.md)
- 配置与 Secret：[docs/backend/配置与Secret运行时说明.md](docs/backend/配置与Secret运行时说明.md)
- 降级错误：[docs/backend/降级策略与错误码说明.md](docs/backend/降级策略与错误码说明.md)
- 观测诊断：[docs/backend/可观测性与诊断说明.md](docs/backend/可观测性与诊断说明.md)
- 数据库迁移：[docs/backend/数据库迁移与版本管理说明.md](docs/backend/数据库迁移与版本管理说明.md)
- 本地开发：[docs/development/本地开发环境说明.md](docs/development/本地开发环境说明.md)
- 管理后台功能：[docs/frontend/管理后台功能与交互说明.md](docs/frontend/管理后台功能与交互说明.md)
- 前端交互：[docs/frontend/前后端交互约束说明.md](docs/frontend/前后端交互约束说明.md)
- 测试验收：[docs/testing/测试与验收策略.md](docs/testing/测试与验收策略.md)
- 模型与检索评测：[docs/testing/模型与检索评测基线.md](docs/testing/模型与检索评测基线.md)
- 备份恢复：[docs/operations/备份与恢复说明.md](docs/operations/备份与恢复说明.md)
- 配置变更：[docs/operations/配置变更操作手册.md](docs/operations/配置变更操作手册.md)
- 工程契约：[docs/contracts/README.md](docs/contracts/README.md)

## 3. 架构边界

后端依赖方向、API / Worker 边界、配置与初始化边界、权限边界、导入索引链路和 RAG 查询链路以 [ARCHITECTURE.md](ARCHITECTURE.md) 为准。

代理修改代码时必须保持：

- route 层不直接访问 MinIO、Qdrant、模型 provider 或复杂 SQL。
- service / facade 承担业务编排、事务边界、权限调用和状态变更。
- repository 只做 SQL 读写，不构造 API response。
- runtime 负责 active config、Secret Store 和外部 adapter 组装。
- presenter 只做展示字段裁剪。
- Worker 不调用 FastAPI route function。
- Permission Service 不依赖 LLM。
- LLM / answer 模块不做权限决策。

如需更详细边界，先读 [ARCHITECTURE.md](ARCHITECTURE.md) 和 [docs/backend/后端架构设计书.md](docs/backend/后端架构设计书.md)。

## 4. 编码约束

### 后端

- Python 文件默认使用 `from __future__ import annotations`。
- 使用 Pydantic v2 模型定义请求、响应和内部 DTO，避免裸 dict 在层间无约束传递。
- 新增 API 必须同时考虑 route、schema、presenter、service、错误映射、权限 scope、OpenAPI 契约和测试。
- route 层必须返回统一错误结构，包含 `request_id`、`error_code`、`message`、`stage`、`retryable` 和必要 `details`。
- 外部 IO 不应长时间占用数据库事务。
- 高风险写操作必须写审计。
- Worker 阶段必须可重试、可接管、可幂等。
- 查询、导入、权限、配置和模型调用相关代码必须传播 `request_id` / `trace_id`。

### 前端

- 使用 Vue 3 Composition API 与 TypeScript。
- API 调用集中在各应用 `src/api/<domain>.ts` 或共享 SDK 中。
- DTO 字段命名保持后端契约原名。
- 认证统一使用 `Authorization: Bearer <jwt>`。
- 前端不得持久化或展示 secret value、完整 token、密码、完整 prompt 或未脱敏敏感原文。
- 管理后台列表视图必须依赖后端分页、筛选和权限过滤。
- 前端错误展示应使用后端结构化错误，不要吞掉 `error_code` 和 `request_id`。

## 5. 权限与安全约束

所有权限、删除、索引和缓存相关改动必须 fail closed。

必须保持：

- draft index、deleted document、blocked document、archived index 不得被查询命中。
- 文档删除和权限收紧先写 access block，再刷新索引或阻断旧索引。
- 查询候选进入上下文前必须经过权限和状态过滤。
- citation unauthorized 必须抑制原答案。
- source 详情读取必须重新鉴权。
- 缓存命中后仍需做 access block 和引用有效性轻量校验。
- 日志、审计、模型调用日志和测试输出不得泄露 password、token、secret value、完整 prompt 或未脱敏敏感原文。

## 6. API 与契约同步

任何 API 非兼容变更必须同步：

- 后端实现。
- `docs/contracts/openapi.yaml`。
- `docs/contracts/权限矩阵.md`。
- `docs/contracts/审计事件字典.md`。
- 前端 API client / SDK / DTO。
- 相关测试。

列表接口必须由后端分页、筛选、权限过滤，并只返回列表展示字段。详情接口必须重新做权限检查。

## 7. 测试与验收

按 [WORKFLOW.md](WORKFLOW.md) 的测试矩阵选择验证命令。

常用最低门禁：

- 后端：`make PYTHON=.venv/bin/python test`
- Qdrant / embedding / 索引：`make PYTHON=.venv/bin/python test-integration-qdrant`
- RAG：`make PYTHON=.venv/bin/python query-regression-rag`
- 普通前端：`npm run typecheck:web`、`npm run build:web`
- 管理后台：`npm run typecheck:admin`、`npm run build:admin`

没有运行应运行的测试时，最终回答必须明确说明原因。

## 8. 文档同步

涉及实现、契约、运行方式、架构边界或验收流程变化时，必须同步更新相关文档。

常见入口：

- [README.md](README.md)
- [docs/README.md](docs/README.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)
- [WORKFLOW.md](WORKFLOW.md)
- `docs/backend/`
- `docs/frontend/`
- `docs/contracts/`
- `docs/operations/`
- `docs/testing/`

成熟文档必须基于当前实现；计划、排查报告和临时清单不能替代 `docs/` 下的成熟文档。

## 9. Git 与工作区

- 修改前用 `git status --short` 判断工作区状态。
- 当前仓库可能存在用户未提交改动，不要还原、格式化或移动与任务无关的文件。
- 如果必须触碰已有脏文件，先理解当前改动并与其兼容。
- 禁止使用 `git reset --hard`、`git checkout -- <file>` 等破坏性命令，除非用户明确要求。

## 10. 回答要求

- 回答使用中文，除非用户明确要求其他语言。
- 不空泛赞美问题；如果用户前提错误，应直接指出。
- 给出结论时标注置信度：高 / 中 / 低 / 未知。
- 代码相关回答应说明修改文件、执行命令、测试结果和剩余风险。
- 如果没有完成、没有运行测试或无法验证，必须直接说明。
