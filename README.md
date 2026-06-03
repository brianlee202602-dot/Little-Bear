# Little Bear

更新时间：2026-06-03

Little Bear 是一个面向企业内部知识检索与问答场景的 RAG 系统工作区。当前仓库已完成 RAG 主链路、服务端全权限知识库自动搜索、P1 Query Rewrite、P2 结构化切块与元数据增强、导入索引 Worker、普通用户查询前端、管理后台核心功能、P0 验收入口，以及后端模块化重构的主要收口工作；前端已完成查询端和管理后台 P0-P13 模块化拆分与样式收口，P14 管理后台大文件二次拆分已继续完成文档弹窗、setup flow、用户表单、角色绑定、配置表单处理、知识库 runtime 和用户 runtime 的职责迁移。

本文只记录项目定位、启动方式、开发约定和当前已完成能力，不承载后续推进说明或任务排期。

## 目录结构

```text
apps/
  api/            FastAPI API
  worker/         导入与索引 Worker
  web/            Vue3 普通前端
  admin/          Vue3 管理后台

packages/
  shared-contracts/
  frontend-sdk/
  ui/

infra/
tests/
docs/                  当前成熟项目文档
design_docs_history/   历史设计文档归档
```

## 现有基础设施

仓库保留了本地开发依赖：

- PostgreSQL
- Redis
- MinIO
- Qdrant
- 本地演示用 TEI embedding / TEI rerank；实际可接入外部 provider 后删除对应 compose service

基础设施当前通过 `Makefile` 封装 Docker Compose 启动：

```bash
make env
make up
make ps
```

PostgreSQL 容器健康后，需要先执行 Alembic 迁移初始化数据库结构。迁移必须在安装了项目 Python 依赖的环境中执行，并且从仓库根目录运行：

```bash
python3 -m alembic.config --version
make PYTHON=python3 db-upgrade
make PYTHON=python3 db-current
```

如果 `python3 -m alembic.config --version` 提示找不到 `alembic`，说明当前解释器不是项目开发环境，需要先激活 venv/conda 环境或显式使用对应环境里的 Python。

## 本地开发入口

当前项目建议通过 `Makefile` 启动。`.env` 只作为本地进程环境来源，不要把真实业务密钥写入 README 或 Makefile。

首次启动先生成本地环境文件并拉起基础设施：

```bash
make env
make up
make ps
```

`.env.example` 已覆盖本地 API、Worker、前端、PostgreSQL、MinIO、Qdrant 联调和 smoke/regression 变量。现有 `.env` 不会被 `make env` 覆盖；如果后续示例新增变量，需要手动按需补入当前 `.env`。

PostgreSQL 就绪后执行数据库迁移：

```bash
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python db-current
```

当前 Alembic 迁移已压缩为一个当前 schema 基线：
`apps/api/migrations/versions/0013_current_schema_baseline.py`。空库执行
`db-upgrade` 会一次性建立当前版本结构；已经升级到
`0013_query_log_scope_summary` 的数据库不会重复执行建表。若某个历史环境仍停留在
`0013` 之前的旧增量版本，需要先使用旧迁移链升级到 head，或重建数据库后再使用当前基线。

启动 API：

```bash
make PYTHON=.venv/bin/python api
```

`make api` 会读取 `$(ENV_FILE)`，默认是 `.env`，并以 reload 模式启动 FastAPI：

```bash
PYTHONPATH=apps/api LOG_LEVEL=INFO .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动导入与索引 Worker：

```bash
make PYTHON=.venv/bin/python worker
```

Worker 不处理 HTTP 请求，它负责消费 `import_jobs`，推进文档导入、解析、切块、embedding、Qdrant 写入和索引发布。上传文档后如果没有启动 Worker，任务会停留在 `queued`。

本地调试多个 Worker 时，不要把 `WORKER_ID` 写死在 `.env`，应在启动命令中为每个实例指定：

```bash
make PYTHON=.venv/bin/python WORKER_ID=import-worker-1 worker
make PYTHON=.venv/bin/python WORKER_ID=import-worker-2 worker
```

也可以使用简写：

```bash
make PYTHON=.venv/bin/python worker-1
make PYTHON=.venv/bin/python worker-2
```

启动普通用户 Web 和管理后台：

```bash
make web
make admin
```

常用本地启动顺序：

```bash
make up
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python api
make PYTHON=.venv/bin/python worker
make web
make admin
```

Qdrant 与 embedding provider 的真实写入/召回联调测试默认不随单元测试运行。启动本地 `qdrant` 和 `tei-embedding` 后，可执行：

```bash
make test-integration-qdrant
```

如果当前 shell 使用项目虚拟环境，可显式指定解释器：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

初始化并导入可查询知识库后，可以执行 P0 主链路 smoke，覆盖登录、知识库浏览、非流式查询和 SSE 查询。执行前需要在 `.env` 或命令行中配置 `LITTLE_BEAR_SMOKE_USERNAME` 和 `LITTLE_BEAR_SMOKE_PASSWORD`，并确保该用户至少能访问一个已发布索引的知识库：

```bash
LITTLE_BEAR_SMOKE_USERNAME=<username> \
LITTLE_BEAR_SMOKE_PASSWORD=<password> \
make PYTHON=.venv/bin/python smoke-p0
```

需要保留脱敏执行记录时使用：

```bash
make PYTHON=.venv/bin/python smoke-p0-record
```

执行查询回归数据集：

```bash
make PYTHON=.venv/bin/python query-regression-p0
```

默认查询回归样例当前归档于 `design_docs_history/examples/query-regression.p0.jsonl`。真实验收时应复制并替换为当前业务知识库的问题、预期引用和必要关键词；执行记录默认写入 `artifacts/`，不会提交到仓库。

RAG 增强回归样例位于 `docs/examples/query-regression.rag-enhancement.jsonl`，覆盖空 `kb_ids` 自动搜索全部可访问知识库、跨文档联合问题、结构化切块命中、口语化问题和低相关降级：

```bash
make PYTHON=.venv/bin/python query-regression-rag
```

该目标仍复用 `tools/query_regression.py`，默认记录写入 `artifacts/query-regression-rag-latest.json`。

管理后台查询日志详情中的检索诊断已展示 Query Rewrite、阶段候选数量、子 query 召回明细、权限 Gate 拒绝摘要、Rerank 摘要和最终上下文片段摘要；诊断内容不包含完整 prompt 或文档原文。

查询日志已新增结构化摘要字段：`query_scope_mode`、`resolved_kb_count` 和 `rewrite_count`。管理后台查询日志列表可显示查询范围、解析出的知识库数量和 rewrite 数量，并支持按查询范围过滤。

普通查询响应已新增 `query_scope` 范围摘要；非流式响应、流式 `metadata` 和流式 `done` 均会返回查询范围模式与最终解析出的知识库数量。完整检索诊断仍仅通过管理后台查询日志详情查看。

查询上下文构建已按 `max_context_tokens` 做 token 预算截断；当前使用可替换的保守 token 估算器，避免联合问题中长 chunk 挤占全部上下文预算。

历史文档结构化元数据补齐策略已整理到 `docs/backend/历史文档元数据补齐策略.md`。现有“重建索引”只重排已有 chunk，不会重新解析原文或补齐旧 chunk 元数据；需要补齐页码、标题路径和结构块 offsets 时，应重新导入或生成新文档版本。

发布前可以使用当前非破坏性 P0 验收目标串联 smoke 记录和查询回归：

```bash
make PYTHON=.venv/bin/python release-smoke-p0
```

该目标要求 API 已完成初始化、至少存在一个当前账号可访问且已发布索引的知识库，并且 `.env` 或命令行已配置 smoke/regression 登录账号。它不会创建、上传或删除业务数据；文档上传、索引重建、权限收紧、删除阻断等写入型验收仍按发布检查清单人工执行并留存记录。

数据库迁移完成后再启动 API。空库完成迁移但尚未执行业务初始化时，`GET /internal/v1/setup-state` 应返回未初始化状态，随后才能进入 `setup-config-validations` 和 `setup-initialization` 流程。

## 开发约定

- 项目代码中的注释、docstring 和面向开发者的说明默认使用中文。
- 注释优先解释设计意图、权限边界、事务边界、幂等、降级和安全限制，不重复描述显而易见的代码行为。
- 错误码、API 字段、数据库字段、配置 key、scope、枚举值和第三方协议术语保持契约中的原始名称。
- 每次代码更新都必须同步更新本 README 中的当前状态或相关说明；后端、前端、脚本、迁移、契约和文档对齐类变更都应同步维护这里的项目说明，避免 README 与实现进度脱节。

## 当前状态

- 文档目录已重新分层：`docs/` 用于存放经过实现校对的成熟项目文档，旧 `docs` 已整体归档为 `design_docs_history/`，用于保留历史设计、模块计划、联调记录和旧契约文档。
- 已新增 `docs/backend/后端架构设计书.md` 和 `docs/backend/后端接口文档.md`，按当前代码实现整理 API、Worker、模块边界、配置密钥、权限、导入索引、查询链路、审计观测、当前实现边界和接口用途说明。
- 运行时配置 Schema 读取和 OpenAPI 契约单测已同步到 `docs/contracts/`；查询回归默认数据集和初始化示例配置路径继续使用历史归档中的测试示例。
- 设计文档和工程契约已收敛，成熟 OpenAPI、数据库 Schema、配置 Schema、权限矩阵、状态机和审计事件字典已迁入 `docs/contracts/`；历史归档中继续保留 MVP、旧模块计划和旧测试计划。
- 文档与实现已完成一轮对照整改：OpenAPI 已挂载接口与契约差异被测试跟踪，P1/P2 contract-only 接口已在文档中标注阶段边界。
- 后端控制面已初步落地：初始化、setup JWT、active config、Secret Store、认证会话、配置管理、用户/部门/角色绑定管理、审计查询和健康检查。
- 后端接口层公共能力已收敛：认证、request_id / trace_id、分页、结构化错误响应、ServiceError 基类和对象存储 runtime 已抽为公共依赖或共享模块。
- 后端 route 层对象存储 runtime 泄漏已收敛：普通用户 citation 来源读取和管理后台文档预览不再由 route 构建 `ObjectStorage`，改由 `KnowledgeService` / `AdminService` 在领域服务内按当前 session 解析对象存储运行时，route 继续只负责认证、参数、分页、错误映射和 service 调用。
- 后端 admin / query / audit 中的 compatibility / legacy 语义残留已清理：相关 facade 和 mixin 已标定为正式的 route-facing、diagnostics-facing 或领域 helper 边界，不再以历史兼容层描述。
- 后端模块化重构已完成 P0-P5 主要任务：Admin、Auth、Audit、Config、Import Pipeline、Indexing、Knowledge、Permission、Query、Setup 等模块已按 service / repository / runtime / writer / presenter 等边界拆分；历史 `core.py` 中间兼容文件已删除，当前 `apps/api/app/modules` 下不再保留 `*core.py`。
- 后端重构期兼容冗余已完成一轮清理：管理后台子路由不再通过聚合路由 `_compat()` 回跳共享依赖，`admin` / `config` / `query` / `import_pipeline` 聚合路由只保留 router 挂载职责；`ConfigRepository` 聚合兼容仓储、`ConfigService` 私有兼容代理、`ImportDocumentWriter.owner` 回调桥、query / knowledge / setup 下划线 mapper/helper 兼容别名，以及 admin 侧旧权限变更服务入口已删除，权限策略修改统一由 `modules.permissions.PermissionAdminService` 承担。
- 数据库迁移已压缩为当前 schema 基线，覆盖配置、认证、组织、权限、知识库、文档、索引、导入任务、审计、查询日志、模型调用日志、查询会话和检索诊断表。
- 管理后台已接入 setup、登录、配置、用户、部门、角色绑定、审计查询和知识库运营页面；知识库页面已支持知识库 CRUD、文件夹 CRUD、指定文件夹上传、文档列表、文档版本、chunk 预览以及知识库 / 文档权限变更。
- Permission Service 核心已落地；管理端知识库、文件夹和文档元数据管理已接入权限边界。
- 权限安全回归测试已补强：跨部门候选、access block、旧索引版本、deleted / draft / pending_delete 非 active 状态、source 回源权限过滤和 citation unauthorized 降级均已纳入单元测试防回退范围。
- 文档详情、文档版本、chunk 来源、普通用户文档预览，以及知识库 / 文档独立权限变更 API 已补齐。
- Import Service、Worker 和 Indexing Service 最小链路已落地：支持上传 / URL / metadata_batch 导入任务创建、任务查询、取消、重试、Worker claim、过期 `running` 任务锁接管、非持锁推进拒绝、失败重试恢复、MinIO/S3 对象存储交接、PDF / DOCX / UTF-8 文本 / Markdown parse-clean-chunk、结构块 `ParsedBlock`、`StructureAwareChunker`、chunk 页码和 `source_offsets` 元数据写入、结构化 keyword/vector 索引文本、draft chunk 写入、PostgreSQL 关键词索引账本、embedding 分批与批量失败拆分重试、Qdrant draft vector point 写入、active index 发布，以及权限变更后的索引 payload 刷新任务。
- Query Service 非流式链路已落地：`POST /internal/v1/queries` 支持关键词召回、query embedding client、Qdrant VectorRetriever adapter、Weighted RRF 融合排序、关键词标题 / heading / tags 字段加权、候选 matched query 归因、CandidateQualityGate、相邻 chunk 权限重检扩展、文档 / section 上限、embedding MMR 去冗余（缺向量时回落文本 Jaccard）、Context Builder 完整 chunk 对象存储回源读取、`query_retrieval_diagnostics` 检索诊断落库、rerank provider、Permission Service filter、候选 gate、LLM provider、citation 校验、query_logs、model_call_logs 和高风险 query audit 写入；多 query 检索时已在 fusion、rerank 输入、权限 gate 前候选配额、按子问题 rerank、最终候选裁剪和 Context Builder 阶段保留子问题覆盖，Context Builder 会按已选 chunk 数量分配多子问题 token 预算，在 LLM prompt 中携带 `matched_query`，避免某个子问题候选被全局排序或上下文压缩挤出；Context Builder 已修复 coverage seed 后继续 MMR 补充候选时的 token set 范围问题，避免显式知识库查询触发 `KeyError`；答案引用已收窄为实际进入 LLM 上下文的 chunk；rerank、LLM 不可用、候选质量过低、完整 chunk 对象不可用或 citation 校验失败时结构化降级或回落。
- Query Service citation 后处理已补强：当模型把引用写成 `[source:1]`、`[source:无相关资料]` 等非法格式或遗漏引用但答案正文仍可保留时，系统会移除错误占位符，并只用本次已授权候选自动补引用；该行为只写入审计摘要，不再作为用户侧降级状态展示。若模型引用合法 UUID 但不属于本次授权来源，或非法引用不可修复，仍按 `citation_unauthorized` / `citation_invalid_format` 拦截并降级。
- RAG P1 Query Rewrite 已落地：新增 `apps/api/app/modules/query_rewrite`，支持规则 fallback 拆分复合问题、保留自包含子问题和最近会话指代补全；例如 `什么是 Can 协议，什么是 RAG` 会被拆为原始问题、`什么是 Can 协议` 和 `什么是 RAG` 三条检索 query。active config 可开启 LLM JSON rewrite，失败时回退规则检索并写入模型调用日志 hash；QueryOrchestrator 已对 rewritten queries 分别执行关键词召回和向量召回，最终上下文构建与回答仍基于用户原始问题。配置契约已支持 `retrieval.query_rewrite_*` 与 `timeout.query_rewrite_ms`。
- Query Stream 和普通用户查询工作区第一版已落地：支持 `POST /internal/v1/query-streams` SSE 输出、provider token 级流式答案、Web 登录、token refresh、知识库浏览、文档浏览、citation 来源跳转、流式/非流式查询、服务端全权限知识库自动搜索、服务端历史会话同步、多轮消息展示、会话删除、降级状态、request_id 和 trace_id 展示；流式 token 生成、查询收束和会话写回阶段已补齐异常兜底，provider 流式裸异常会进入 LLM 降级结果，收束异常会返回 SSE `error` 事件并标记会话消息失败，避免 generator 异常直接击穿为 ASGI 500。
- 普通用户查询前端已完成模块化拆分和工作区运行态下沉，并新增 `docs/frontend/查询前端架构设计书.md` 作为团队开发架构说明：`App.vue` 只挂载 `ChatWorkspace.vue`，跨域编排迁入 `useChatWorkspaceRuntime.ts`；HTTP 层、认证会话、会话列表、知识库选择、聊天输入、流式查询执行、消息列表、来源片段预览和浏览器存储已拆入 `apps/web/src/features`、`apps/web/src/components`、`apps/web/src/utils` 和 `apps/web/src/api`。`useQueryStream` 已改为依赖会话窄接口，SSE 事件已补 runtime guard，避免弱类型事件直接写入消息状态；查询输入区已固定在浏览器视口底部，消息列表在工作区内部滚动，用户无需滑到页面底部即可继续输入。
- 普通用户查询前端已修复历史会话消息排序：刷新页面、切换会话和加载历史消息时，会按时间线归一化消息顺序；同一轮问答使用 `createdAt + debugId` 聚组，并保证用户提问显示在对应回答上方。
- 管理后台前端已完成 P0-P4 模块化重构：公共 HTTP 层、通用工具、基础组件、后台外壳、菜单权限、初始化页面、配置管理、部门管理、用户管理和角色绑定已拆入 `apps/admin/src/features`、`apps/admin/src/components`、`apps/admin/src/composables` 和 `apps/admin/src/app`；配置、部门、用户相关请求和状态已分别迁移到对应 composable。
- 管理后台知识库管理前端已完成 P5 拆分：知识库主列表页、知识库操作弹窗、文件夹操作弹窗、文档管理弹窗、文件夹管理面板、文档权限 / 版本片段弹窗已抽入 `apps/admin/src/features/knowledge`；知识库列表、详情、权限、文件夹、文档、导入上传、版本片段、批量索引等主要操作逻辑已迁入 `useKnowledgeBaseAdmin.ts`；`apps/admin/src/App.vue` 已从约 14102 行降至约 7654 行。
- 管理后台运维诊断审计前端已完成 P6 拆分：索引运维、Qdrant 快照、查询日志、查询详情、模型调用日志、模型调用详情和配置审计日志已抽入 `apps/admin/src/features/diagnostics` 与 `apps/admin/src/features/audit`；查询日志详情已接入 `query_retrieval_diagnostics` 检索诊断可视化，展示 query rewrite、阶段候选数量、quality gate 和最终上下文片段摘要；诊断请求状态已迁入 `useDiagnostics.ts`，配置审计请求状态已迁入 `useAuditLogs.ts`，降级原因短中文描述和诊断状态 tone 已迁入 `apps/admin/src/utils/status.ts`；`apps/admin/src/App.vue` 当前约 6337 行。
- 前端 API client 已完成 P7 收口：普通查询端 API 已拆为 `auth`、`knowledge`、`documents`、`conversations`、`query`、`health` 和 `types` 模块，页面和 composable 已直接 import 具体 API 模块，不再保留 `apps/web/src/api/client.ts` 兼容聚合入口；管理后台 API 已拆为 `setup`、`auth`、`config`、`audit`、`diagnostics`、`departments`、`users`、`roles`、`knowledgeBases`、`folders`、`documents`、`imports`、`indexOps` 及各领域类型模块，管理后台不再保留 `apps/admin/src/api/client.ts` / `apps/admin/src/api/types.ts` 兼容聚合入口。
- 前端样式已完成 P8 收口：普通查询端 `App.vue` 已移除大块 scoped style，样式拆入 `apps/web/src/styles/tokens.css`、`base.css` 和 `chat.css`；管理后台 `App.vue` 已移除全局 style，样式拆入 `apps/admin/src/styles/tokens.css`、`base.css`、`layout.css`、`ui-controls.css`、`list-filter-layouts.css`、`entity-tables.css`、`modals.css`、`pickers.css`、`setup-layout.css`、`setup-forms.css`、`setup-feedback.css` 和 `responsive.css`；旧的列表筛选和分页全局规则已按组件结构调整，并已通过 mock 运行态截图验证查询端、管理后台主页面和代表性弹窗在桌面宽度下无横向溢出、无离屏按钮、无 console error。
- 管理后台启动与认证已完成 P9 深拆：`apps/admin/src/App.vue` 只挂载 `AdminRoot`，登录页迁入 `apps/admin/src/app/LoginPage.vue`，setup-state / active view / 路径同步、管理员会话 token / 登录恢复 / 退出、tab 切换分别迁入 `useAdminBootstrap.ts`、`useAdminSession.ts` 和 `useAdminNavigation.ts`；本轮已通过管理后台 typecheck 和 build。
- 管理后台 setup 域已完成 P10 深拆：初始化表单、payload、后端校验、初始化提交、字段更新和页面派生状态已迁入 `apps/admin/src/features/setup/useSetupFlow.ts`；本地确定性校验迁入 `setupValidation.ts`，结构化错误 / bootstrap check / database error 提取迁入 `setupErrors.ts`；`SetupPage.vue` 已改为消费单一 setup flow。
- 管理后台用户、部门和角色绑定已完成 P11 深拆：部门弹窗表单与可操作状态迁入 `useDepartmentModals.ts`，用户新增 / 编辑 / 删除 / 密码重置状态迁入 `useUserModals.ts`，用户部门绑定分页和主部门替换确认迁入 `useUserDepartmentBindings.ts`，角色候选、作用域默认选择和高风险确认迁入 `useUserRoleBindings.ts`；部门与角色展示文案迁入 `departmentDisplay.ts` / `userDisplay.ts`；`DepartmentManagementPanel.vue` 和 `UserManagementPanel.vue` 负责组装列表与弹窗。
- 管理后台知识库域已完成 P12 深拆：知识库 / 文件夹 / 文档权限 / 上传 / 索引重建 modal 与表单状态迁入 `useKnowledgeModals.ts`，父知识库权限校验和 ACL 规则构建迁入 `useKnowledgePermissions.ts`，文档详情、版本 / chunk、批量重建和索引清理选择迁入 `useDocumentSelection.ts`，知识库 / 文件夹 / 文档 / 导入任务 / 索引版本 / chunk 展示文案迁入 `knowledgeDisplay.ts`；`KnowledgeBaseAdminContainer.vue` 负责组装知识库列表与相关弹窗。
- 管理后台展示工具与上下文已完成 P13 收口：状态文案、tone、布尔值、耗时、token 用量、审计时间、短 ID、分页、结构化错误和集合去重已分别迁入 `apps/admin/src/utils/display.ts`、`date.ts`、`pagination.ts`、`errors.ts` 和 `collections.ts`；audit、diagnostics、knowledge、department、user 页面 model 已改为各 feature 内部的命名上下文类型，`apps/admin/src/features` 与 `apps/admin/src/app` 下不再使用 `Record<string, any>` 页面 ctx。
- 管理后台知识库管理 composable 已完成大文件二次拆分：`apps/admin/src/features/knowledge/useKnowledgeBaseAdmin.ts` 当前约 199 行，只负责组装 options、import jobs、documents、folders、records、upload、refresh 和 access selection 子域；知识库刷新编排、记录 CRUD、上传导入、访问部门勾选已分别迁入 `useKnowledgeBaseAdminRefresh.ts`、`useKnowledgeBaseRecords.ts`、`useKnowledgeBaseUpload.ts` 和 `useKnowledgeBaseAccessSelection.ts`，并已通过 `npm run typecheck:admin` 与 `npm run build:admin`。
- 管理后台根组件已完成运行态迁移：`apps/admin/src/app/AdminRoot.vue` 当前约 55 行，只负责 loading、登录、dashboard 和 setup 顶层视图分支；原根组件中的认证、setup、能力、导航迁入 `useAdminAppRuntime.ts`，dashboard tab 与页面容器挂载迁入 `AdminDashboard.vue`；配置、部门、用户、知识库、诊断等业务域运行态已迁入各自 `features/<domain>/<Domain>Feature.vue`，旧 app 级 `adminContexts.ts`、`useAdminDomainContexts.ts`、`contexts/knowledgeContext.ts` 和 `useAdminDisplayLookups.ts` 已删除。
- 管理后台构建入口已完成首轮按需加载优化：`featureRegistry.ts` 中配置、部门、用户、知识库和诊断 feature 已改为 `defineAsyncComponent` 动态 import，`AdminRoot.vue` 中初始化 `SetupPage` 也已改为动态加载；管理后台首包不再同步打入所有业务页面。异步加载后已将 `.panel`、`.button`、`.field`、`.control`、`.summary`、`.tone` 等通用 UI 样式接入全局 `ui-controls.css`，避免继续依赖 setup 页面静态导入带来的样式副作用。
- 管理后台前端架构专项重构已完成 P0-P12 前端代码门禁：已新增 `docs/frontend/管理后台前端架构设计书.md`，用于记录团队开发架构约束；`AdminRoot.vue` 已 provide session、capability、navigation 和 typed event bus，`AdminDashboard.vue` 已通过 provider 获取 shell 运行态；新增 `featureRegistry.ts` 与 `AdminFeatureOutlet.vue`，dashboard 不再硬编码具体业务页面；部门、配置、诊断、用户、知识库管理页已迁入各自 `features/<domain>/<Domain>Feature.vue` 自持运行态；根运行态已重命名为 `useAdminAppRuntime.ts` 并收缩为 app lifecycle / session / capability / navigation / setup 状态，不再 import 业务域 runtime 或 feature display helper；P10 已移除 app outlet legacy `ctx`、知识库组件 `ctx` 命名、诊断 / 配置 / 用户 / 知识库 action 的显式 `any` option bag，并完成用户管理与知识库管理聚合 model、知识库文档 / 知识库记录 action 聚合点的明确类型建模；P11 已将配置、诊断、知识库文档和 setup 专属样式改为由 feature 入口加载，全局样式只保留 tokens、base、layout、通用筛选布局、通用表格、modal、选择器和响应式规则；P12 已通过 `npm run typecheck:admin`、`npm run build:admin`、架构约束扫描和生产预览首页 200 验证。当前 `apps/admin/src/app`、`features`、`components`、`composables`、`utils` 范围内显式 `any` 扫描无命中。
- 管理后台已从“模板拆分”进入“状态所有权迁移”：部门域列表、部门 options、搜索表单、分页、busy、feedback 和部门弹窗表单已迁入 `apps/admin/src/features/departments/useDepartmentAdminRuntime.ts`；用户域列表、用户详情、用户搜索分页、用户弹窗、部门绑定、角色绑定和用户 CRUD action 已迁入 `apps/admin/src/features/users/useUserAdminRuntime.ts`；知识库、文件夹、文档、导入任务、失败索引任务、文档批量选择、知识库权限和文档权限运行态已迁入 `apps/admin/src/features/knowledge/useKnowledgeAdminRuntime.ts`，并继续拆出 `useKnowledgeAdminState.ts`、`useKnowledgeDerivedState.ts`、`useKnowledgeFailedIndexJobs.ts`、`useKnowledgeDocumentIndexState.ts`、`useKnowledgeAdminReset.ts` 和 `knowledgeDepartmentLookup.ts`。`AdminRoot.vue` 不再直接创建或清空部门 / 用户 / 知识库域状态，只消费领域 runtime 暴露的状态和动作。
- 管理后台配置与诊断 composable 已完成大文件拆分：`useConfigManagement.ts` 只保留配置列表、弹窗和版本状态编排，配置表单回填、配置 section 合并和值类型兜底已分别迁入 `configFormHydration.ts`、`configSectionMerge.ts` 和 `configValueCoercion.ts`，配置版本 API action 迁入 `useConfigVersionActions.ts`；`useDiagnostics.ts` 当前约 327 行，索引运维动作迁入 `useIndexDiagnostics.ts`，Qdrant 快照 / 恢复 / 重建索引动作迁入 `useIndexSnapshotDiagnostics.ts`，查询日志 / 模型调用日志动作迁入 `useLogDiagnostics.ts`。
- 管理后台知识库多模式弹窗和大型 CSS 已完成第一轮拆分：`KnowledgeBaseModal.vue` 当前约 334 行，新增知识库、上传、重建索引、删除模式分别迁入 `KnowledgeBaseCreateForm.vue`、`KnowledgeBaseUploadForm.vue`、`KnowledgeBaseIndexRebuildPanel.vue` 和 `KnowledgeBaseDeletePanel.vue`；`operations.css` 和 `setup-controls.css` 兼容 facade 已删除，入口样式改为直接 import `entity-tables.css`、`modals.css`、`pickers.css`、`setup-layout.css`、`setup-forms.css` 和 `setup-feedback.css`。
- 管理后台 P14 已继续完成剩余大文件拆分：`setupDefaults.ts` 过渡 facade 已删除，初始化模型、默认值和 payload builder 分别由 `setupModel.ts`、`setupDefaultValues.ts` 和 `setupPayloadBuilder.ts` 直接提供；`setupFields.ts` 已按字段类型、基础初始化、模型切片和策略高级拆分；`useSetupFlow.ts` 已进一步拆为 setup 状态容器、派生状态、远程动作、字段写入和状态文案模块；`useUsers.ts` 已拆为账号、部门归属和角色绑定动作；`useUserAdminRuntime.ts` 已迁出用户域刷新、弹窗动作和基础状态；`useUserRoleBindings.ts` 已迁出角色候选、作用域默认选择和绑定刷新；`UserFormModal.vue` 已拆为新增、编辑、删除三个子表单；`KnowledgeBaseListPage.vue` 已迁出导入任务 / 失败索引任务区；`DocumentPermissionModal.vue` 已拆为权限编辑、文档版本、索引版本、Chunk 预览和详情壳组件；`useKnowledgeBaseRecords.ts` 已迁出知识库 modal、索引动作、CRUD action 和记录映射；`useKnowledgeDocuments.ts` 已迁出文档加载和文档索引动作；`useKnowledgeAdminRuntime.ts` 已迁出知识库 runtime 派生切片；`useKnowledgePermissions.ts` 已迁出权限类型和 ACL 规则。管理后台 feature 文件当前已无超过 450 行的大文件。
- 管理后台文档详情弹窗已完成版本区展示收口：文档版本、索引版本和 Chunk 预览在单页数据时不再显示无效分页控件，文档版本卡片与索引版本面板的网格比例已调整，避免刷新后出现窄列分页挤压和元素排列失衡。
- 管理后台索引运维健康检查已补齐仓储层 SQL 回归防护：`/internal/v1/admin/index-health` 的 collection health 查询已修复 CTE 分隔错误，避免刷新索引健康列表时因 SQL 语法异常返回 `INDEX_HEALTH_UNAVAILABLE`。
- 已新增 P0 主链路 smoke 脚本、脱敏执行记录和查询回归数据集入口；`employee` 内置角色已补齐 `knowledge_base:read` 初始化模板和存量迁移。
