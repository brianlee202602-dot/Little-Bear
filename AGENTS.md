# AGENTS.md instructions for /Users/brian/编码/Python/Little-Bear

本文件适用于整个仓库。所有自动化编码代理在修改本项目时，必须优先遵守这里的项目事实、架构边界和质量门禁；若与更高优先级的系统/平台指令冲突，以更高优先级指令为准。

## 项目定位

Little Bear 是面向企业内部知识检索与问答的 RAG 系统工作区，目标是让用户只能检索自己有权限访问的资料，并在批量导入、模型服务波动和高并发查询下保持可降级、可审计、可恢复。

当前仓库包含：

- `apps/api`：FastAPI API 服务。
- `apps/worker`：导入、解析、切块、embedding、索引发布 Worker。
- `apps/web`：Vue 3 普通用户前端。
- `apps/admin`：Vue 3 管理后台。
- `packages/shared-contracts`：前后端共享契约包。
- `packages/frontend-sdk`：前端 API SDK 包。
- `packages/ui`：共享 UI 包。
- `docs`：架构、模块、OpenAPI、数据库、权限、状态机、测试和运维文档。
- `tests`：单元、集成、契约和端到端测试目录。

## 技术栈

后端：

- Python `>=3.12`。
- FastAPI + Uvicorn。
- Pydantic v2 + pydantic-settings。
- SQLAlchemy 2.x + Alembic。
- PostgreSQL，使用 `psycopg[binary]` 驱动。
- JWT 使用 `PyJWT`；密码哈希使用 `argon2-cffi`。
- 文档解析最小链路包含 `pypdf`，DOCX / UTF-8 文本 / Markdown 解析能力按现有模块实现扩展。
- 结构化日志使用 `python-json-logger`。
- JSON Schema 校验使用 `jsonschema`。
- 加密相关能力使用 `cryptography`。

前端：

- npm workspaces。
- Vue 3.5 + TypeScript 5.9。
- Vite 7。
- `vue-tsc` 做类型检查。
- `@/*` 指向各应用自己的 `src/*`。
- `apps/web` 默认 dev 端口 `5173`，`apps/admin` 默认 dev 端口 `5174`。
- 前端 dev server 代理 `/internal` 和 `/health` 到 `http://127.0.0.1:8000`。

基础设施：

- PostgreSQL：业务事实源、元数据、权限、配置、任务、审计、查询日志、模型调用日志和关键词索引账本。
- Redis：缓存、锁、限流、配置通知等派生运行能力。
- MinIO：原始文件、解析结果、清洗结果和大文本对象。
- Qdrant：chunk 向量索引及权限 payload。
- TEI embedding / TEI rerank：本地演示和联调用模型服务；真实部署可替换为外部 provider。
- OpenAI-compatible LLM provider：由初始化后的 active config 指定。

## 启动与常用命令

优先使用 `Makefile` 中的命令，不要手写一套不一致的启动方式。

- 生成本地环境文件：`make env`
- 启动基础设施：`make up`
- 查看容器状态：`make ps`
- 查看日志：`make logs`
- 停止基础设施：`make down`
- 删除本地 volume 重置：`make reset`
- 执行迁移：`make PYTHON=.venv/bin/python db-upgrade`
- 查看迁移版本：`make PYTHON=.venv/bin/python db-current`
- 启动 API：`make PYTHON=.venv/bin/python api`
- 启动 Worker：`make PYTHON=.venv/bin/python worker`
- 启动普通前端：`make web`
- 启动管理后台：`make admin`
- 后端快速门禁：`make PYTHON=.venv/bin/python test`
- Qdrant / embedding 真实联调：`make PYTHON=.venv/bin/python test-integration-qdrant`
- P0 主链路 smoke：`make PYTHON=.venv/bin/python smoke-p0`
- P0 查询回归：`make PYTHON=.venv/bin/python query-regression-p0`
- 发布前 P0 smoke + 查询回归：`make PYTHON=.venv/bin/python release-smoke-p0`
- 前端构建：`npm run build:web`、`npm run build:admin`
- 前端类型检查：`npm run typecheck:web`、`npm run typecheck:admin`

迁移必须从仓库根目录运行，并确保当前 Python 环境已安装项目依赖。PostgreSQL ready 之后先跑 Alembic，再启动业务初始化和 API。

## 架构边界

后端采用模块化单体 + 轻量 Worker。依赖方向必须保持单向：

```text
api/routes -> api/dependencies / api/presenters / api/schemas
api/routes -> modules/<domain> service/facade
modules/<domain> service/facade -> repository / policy / runtime / shared / db
runtime -> config / secrets / adapters
adapters -> 外部系统
```

禁止方向：

```text
modules -> api/routes
modules -> api/schemas
shared -> modules
adapters -> modules
db -> modules
worker -> FastAPI route function
api/routes -> qdrant/minio/model provider SDK
api/routes -> 复杂 SQL 或业务权限决策
permission module -> LLM
LLM / answer module -> permission decision
```

职责约束：

- `api/routes` 只处理 HTTP 入参、认证依赖、分页、状态码、调用 service/facade、调用 presenter。
- `api/dependencies` 只封装 FastAPI dependency、认证、request_id、分页和公共 header，不写业务数据。
- `api/schemas` 只定义 API DTO，禁止依赖 `modules/*`，禁止 admin/public DTO 互相复用。
- `api/presenters` 只做 service 返回值到 API schema 的映射和展示字段裁剪，禁止查库、鉴权、调用外部 provider。
- `modules/<domain>` 承担业务规则、事务编排、权限校验调用、状态变更；只暴露清晰 service/facade。
- `repository.py` 集中模块 SQL 读写，禁止构造 API response、调用外部 provider 或做复杂权限决策。
- `runtime.py` 基于 active config、secret 和运行参数组装 adapter / provider / writer / reader。
- `shared` 只能放无业务归属的错误、时间、ID、分页、日志、request_id 等通用能力。
- `adapters` 只封装外部系统 SDK 或 HTTP 协议差异，不读数据库，不依赖业务 service。
- `db` 只放连接、session、metadata、migration 相关能力。

## 配置与初始化规范

启动层只允许读取数据库连接配置和不参与业务决策的进程参数：

- `DATABASE_URL`
- `DATABASE_CONNECT_TIMEOUT_SECONDS`
- `DATABASE_POOL_SIZE`
- `DATABASE_POOL_MAX_OVERFLOW`
- `DATABASE_SSL_MODE`
- `APP_ENV`
- `SERVICE_NAME`
- `API_HOST`
- `API_PORT`
- `LOG_LEVEL`

业务配置禁止直接从环境变量读取，包括 Redis、Secret Provider、MinIO、Qdrant、embedding、rerank、LLM、检索策略、权限策略、缓存策略、限流策略和审计策略。业务模块必须通过数据库 active config 和 `ConfigService` 获取这些配置。

初始化约束：

- 空库先执行 Alembic migration，再走 setup API。
- 数据库连接缺失或 PostgreSQL 连接失败时，进程启动失败或 readiness=false，不进入 setup mode。
- 系统未初始化时，只开放 setup-state、setup-config-validations、setup-initialization 和符合生命周期门禁的 healthcheck。
- 初始化成功后，必须存在 active config，ServiceBootstrap 完成关键模块初始化后才能开放普通业务 API。
- initialized=true 但 active config 缺失、损坏或关键模块 bootstrap 失败时，进入拒绝模式并告警，不回退到环境变量业务配置。
- setup JWT 只能访问 setup validate / initialize，不能访问普通业务 API 或管理 API。

## 后端编码规范

- Python 文件默认添加 `from __future__ import annotations`，保持现有类型标注风格。
- 使用 Pydantic v2 模型定义请求、响应和内部 DTO；不要把裸 dict 在层间无约束传递。
- 新增 API 必须同时考虑 route、schema、presenter、service、错误映射、权限 scope、OpenAPI 契约和测试。
- route 层必须捕获模块错误并返回统一错误结构，包含 `request_id`、`error_code`、`message`、`stage`、`retryable` 和必要 `details`。
- route 层不得直接写复杂 SQL，不得直接构造 MinIO/Qdrant/模型 provider，不得绕过 Permission Service。
- 应用服务负责事务边界；不要在 route、adapter 中散落开启业务事务。
- 外部 IO 不应长时间占用数据库事务。
- 高风险写操作必须写审计，并与核心状态变更保持清晰事务边界。
- Worker 阶段必须可重试、可接管、可幂等；更新任务时检查 `locked_by` 和 `locked_until`。
- 查询、导入、权限、配置、模型调用相关代码必须携带和传播 `request_id` / `trace_id`。
- 错误码、API 字段、数据库字段、配置 key、scope、枚举值和第三方协议术语保持契约中的英文原名。
- 注释、docstring 和面向开发者的说明默认使用中文；注释解释设计意图、权限边界、事务边界、幂等、降级和安全限制，不重复描述显而易见的代码行为。
- 普通日志、审计摘要和测试输出不得包含 secret value、token、密码、完整 prompt、文档原文或未脱敏个人信息。

Python 质量工具以 `pyproject.toml` 为准：

- Ruff line length：`100`。
- Ruff target：`py312`。
- Ruff lint：`E`、`F`、`I`、`UP`、`B`。
- Alembic migration 允许忽略 `E501`。
- Pytest testpaths：`tests`。
- Pytest pythonpath：`apps/api`、`apps/worker`。
- Pytest asyncio mode：`auto`。

## 前端编码规范

- 使用 Vue 3 Composition API 与 TypeScript。
- API 调用集中在各应用 `src/api/client.ts` 或共享 SDK 中，组件不要散落拼接后端 URL。
- 管理后台和普通前端的 DTO 必须匹配 `docs/contracts/openapi.yaml` 和后端 `api/schemas`；字段命名保持后端契约原名。
- 认证统一使用 `Authorization: Bearer <jwt>`。
- 前端不得持久化或展示 secret value、完整 token、密码、完整 prompt 或未脱敏敏感原文。
- 错误展示应使用后端返回的 `error_code`、`message`、`request_id` 或 `debug_id`，不要吞掉结构化错误。
- 管理后台列表视图必须依赖后端分页、筛选和权限过滤，不在前端假分页替代后端权限边界。
- 前端变更至少运行对应应用的 `npm run typecheck:*` 或 `npm run build:*`；涉及用户主链路时同时验证 `web` 和 `admin`。

## API 与契约规范

- OpenAPI 契约文件是 `docs/contracts/openapi.yaml`。
- 权限矩阵是 `docs/contracts/权限矩阵.md`。
- 审计事件字典是 `docs/contracts/审计事件字典.md`。
- 状态机设计是 `docs/contracts/状态机设计.md`。
- 配置 schema 是 `docs/contracts/config.schema.json` 和 `docs/contracts/config-schema.md`。
- 数据库 schema 设计是 `docs/contracts/database-schema.md`。

任何 API 非兼容变更必须同步更新：

- 后端实现。
- `docs/contracts/openapi.yaml`。
- 权限矩阵。
- 审计事件字典。
- P0 测试用例。
- 前端 API client / SDK / DTO。

列表接口必须满足：

- 后端分页：`page`、`page_size`、`total`。
- 后端筛选：如 `keyword`、`status`、`department_id`、`kb_id`、`date_range`。
- 后端权限过滤。
- 只返回列表展示字段。

列表接口禁止返回完整配置、完整权限策略、内部 hash、trace/request 内部 ID、全文 chunk、完整 prompt 或文档原文。

## 权限与安全边界

权限由 RBAC 和文档可见性共同构成。P0 文档可见性只支持：

- `department`
- `enterprise`

不支持上级部门、子部门、项目组、指定用户 ACL、自定义组织 ID 共享或任意用户级文档 ACL。收到这些策略应拒绝，而不是偷偷兼容。

查询候选进入上下文前必须同时满足：

- 权限过滤条件已下推到向量检索和关键词检索。
- `document.lifecycle_status = active`。
- `document.index_status = indexed`。
- `chunk.status = active`。
- `index_version.status = active`。
- `chunk_index_ref.visibility_state = active`。
- 不存在有效 `access_block`。
- 索引权限版本未落后，或已完成回源确认。

权限、删除、索引和缓存必须 fail closed：

- draft index、deleted document、blocked document、archived index 不得被查询命中。
- 文档删除和权限收紧先写 access block，再异步刷新或删除索引。
- 查询缓存 key 必须包含企业、用户或权限过滤 hash、请求过滤条件、配置版本、active index 版本、模型路由和 Prompt 版本。
- 权限刷新中、引用校验失败或降级不完整的响应不得缓存最终答案。
- 缓存命中后仍需做 access block 和引用有效性轻量校验。

## 数据库规范

- PostgreSQL 是业务事实源；Redis、Qdrant、MinIO 和关键词索引均视为派生状态或外部状态。
- 所有租户业务表必须保留 `enterprise_id`，global 表必须明确 scope。
- ID 使用 `uuid`；时间使用 `timestamptz` 并统一 UTC 存储；JSON 使用 `jsonb`；hash 使用稳定 hash 文本。
- 状态字段使用契约定义的枚举值，当前 P0 migration 可使用 `text + CHECK`。
- 数据库约束、唯一索引、partial unique、外键、状态字段和审计关联必须在 migration 中表达，不只靠 service 约定。
- Alembic migration 必须可从空库执行到 head。
- 不要手工改已发布 migration 的语义来“修历史”；新增修正 migration。
- ORM metadata 命名约定见 `apps/api/app/db/base.py`，新增约束应遵守命名 convention。
- 软删除必须有 `deleted_at` 或 access block；不能依赖物理删除保证查询安全。
- 文档、chunk、权限快照、索引版本、chunk index ref 和 access block 是查询可见性的关键事实源，修改时必须同步考虑 Permission Service、Indexing Service 和 Query Service。

## 导入、索引与查询规范

导入链路：

```text
API 校验权限/大小/幂等键
-> 创建 import_job / document / document_version
-> 原始文件写入对象存储
-> Worker claim
-> parse -> clean -> chunk -> embed
-> draft vector / keyword index 写入
-> 校验数量、维度、权限 payload、draft 可见性
-> 原子发布 active index version
-> 写任务状态和审计
```

要求：

- 导入任务必须幂等，正式状态以 PostgreSQL 为准。
- Worker 崩溃后依靠 `locked_until` 释放任务，下一 Worker 可继续领取。
- draft 索引发布前对查询不可见。
- 索引发布前必须校验 chunk 数量、向量维度、payload hash、权限快照和 index version。
- Qdrant 或关键词索引写入失败时不得发布 active index。

查询链路必须保留：

- 鉴权和限流。
- Permission Service 构建权限上下文。
- active config、知识库策略和 active index versions 加载。
- query embedding、向量召回、关键词召回、融合、rerank、candidate gate。
- Context Builder、LLM 调用、citation 校验、权限二次校验。
- query_logs、model_call_logs、审计和降级标记。

降级要求：

- embedding 失败时可降级关键词检索。
- rerank 超时时使用融合分数。
- LLM 超时时返回检索结果和引用，不输出无引用答案。
- citation 校验失败时抑制最终答案或结构化降级。
- 任何降级都必须写入响应、查询日志、模型调用日志或审计摘要。

## 测试要求

后端日常快速门禁：

```bash
make PYTHON=.venv/bin/python test
```

该命令执行：

```text
ruff check apps/api tests tools
pytest -q tests/unit
```

前端门禁：

```bash
npm run typecheck:web
npm run typecheck:admin
npm run build:web
npm run build:admin
```

外部依赖联调：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

P0 验收：

```bash
make PYTHON=.venv/bin/python smoke-p0
make PYTHON=.venv/bin/python query-regression-p0
make PYTHON=.venv/bin/python release-smoke-p0
```

新增或修改功能时，测试覆盖应按风险扩展：

- 纯规则：policy 单元测试。
- 业务编排：service 用例测试。
- SQL、约束、索引、状态迁移：repository / 数据库测试。
- 外部依赖：adapter 集成测试。
- HTTP 契约：API contract 测试。
- 权限边界：权限绕过测试。
- 查询、导入、索引、模型调用：降级、超时、重试和幂等测试。
- 前端 DTO 或接口变更：前端 typecheck/build，并同步 API client。

高风险场景必须自动化，不能只靠手工验收：

- 未初始化时访问普通业务 API。
- setup JWT 越权访问普通业务或管理员 API。
- refresh token 调用普通业务 API。
- 无 scope、错 scope、过期 token 访问受保护接口。
- 普通用户调用管理员接口。
- 跨部门、跨企业、缓存串权和旧权限版本越权。
- draft index、deleted document、blocked document、archived index 被查询命中。
- 权限收紧后旧缓存或旧索引继续可见。
- 日志、审计、模型调用日志泄露 password、token、secret value、完整 prompt 或未脱敏敏感原文。

## 文档同步要求

变更前优先阅读相关文档：

- 总体架构：`docs/架构设计文档.md`
- 公共实现约束：`docs/modules/00-公共实现约束.md`
- 后端模块边界：`docs/architecture/backend-module-boundaries.md`
- 本地开发：`docs/development/本地开发环境.md`
- 测试计划：`docs/testing/测试计划.md`
- 部署发布：`docs/operations/部署与发布检查清单.md`

涉及模块实现时，同时阅读对应 `docs/modules/<编号>-*.md`。代码、测试、OpenAPI、权限矩阵、状态机、审计字典和前端 SDK 必须保持一致；不允许只改实现不改契约。

## Git 与工作区要求

- 当前仓库可能存在用户未提交改动；不要还原、格式化或移动与任务无关的文件。
- 修改前用 `git status --short` 判断工作区状态。
- 只改任务相关文件；若必须触碰已有脏文件，先理解当前改动并与其兼容。
- 禁止使用 `git reset --hard`、`git checkout -- <file>` 等破坏性命令，除非用户明确要求。
- 不提交 `.env`、真实密钥、token、密码、完整 prompt、业务文档原文、测试运行产物或 `artifacts/` 下的敏感记录。

## 协作与回答偏好

- 回答使用中文，除非用户明确要求其他语言。
- 回答前不要空泛赞美问题或默认肯定用户前提；若用户前提错误，应直接指出。
- 给出结论时标注置信度：高 / 中 / 低 / 未知。
- 对不确定事实直接说明未知，并通过代码、文档或可执行命令验证。
- 解释技术判断时先给关键反驳或风险，再给支持理由。
- 代码相关回答应给出具体文件、命令、测试结果和剩余风险，不要只给抽象建议。
