# 前端与管理后台 API 设计实现文档

## 1. 模块目标

本文定义 Little Bear RAG 后端面向普通前端、管理后台、内部系统和运维场景的 RESTful API 边界，补齐知识库、文件夹、文档、审计、查询日志、任务列表和会话刷新等前端必需接口。

本文是 API 路径和请求方法的统一规范。各业务模块文档负责说明业务规则、状态机和模块实现。

## 2. RESTful 设计约定

### 2.1 路径规范

- 路径使用名词复数资源，例如 `/knowledge-bases`、`/documents`、`/import-jobs`。
- 禁止在路径中使用动词动作，例如 `:upload`、`:import`、`:cancel`、`:retry`、`:publish`、`:rollback`、`:disable`。
- 状态变化使用 `PATCH` 修改资源状态，例如禁用、归档、恢复。
- 删除使用 `DELETE`；如果底层是软删除，仍使用 `DELETE`，由服务端写 tombstone 或 access block。
- 需要表达业务动作时，将动作建模为资源，例如 `document-imports`、`job-retries`、`config-validations`、`config-rollbacks`。
- 管理后台接口保留 `/admin` 前缀作为访问边界，但 `/admin` 后仍使用资源名词。

### 2.2 方法语义

| 方法 | 语义 |
| --- | --- |
| `GET` | 读取资源、列表、详情、查询结果 |
| `POST` | 创建资源，或创建一次任务/校验/导入/重试/回滚请求 |
| `PUT` | 整体替换幂等资源，例如用户部门集合、用户角色集合、资源权限策略 |
| `PATCH` | 部分更新资源，例如名称、状态、归属部门、可见性 |
| `DELETE` | 删除或软删除资源，服务端负责阻断和审计 |

### 2.3 API 分层

| API 类型 | 使用方 | 说明 |
| --- | --- | --- |
| 普通前端 API | 企业员工、内部门户、IM Bot | 登录、查询、文档查看、个人可访问知识库 |
| 管理后台 API | system_admin、department_admin、knowledge_base_admin、security_admin、audit_admin | 用户、组织、知识库、文档、权限、配置、审计、任务管理 |
| 初始化 API | 初始化页面、受控部署流程 | 仅未初始化或恢复初始化时开放 |
| 内部服务 API | 后端模块、Worker、Model Gateway | 不允许浏览器前端直接访问 |
| 运维 API/CLI | 运维人员、部署平台 | healthcheck、setup token 签发、索引检查、任务重试 |

当前 P0 后端规范路径统一使用 `/internal/v1`。OpenAPI、后端路由、前端 SDK 和测试均以该路径为准。

## 3. 通用约定

### 3.1 鉴权

- 除 `GET /internal/v1/setup-state`、`POST /internal/v1/sessions`、`POST /internal/v1/token-refreshes`、`GET /health/live`、`GET /health/ready` 外，默认都需要 `Authorization: Bearer <jwt>`。
- 普通前端使用 `access` JWT。
- 管理后台使用普通用户 `access` JWT，再由 Permission Service 校验管理 scope。
- 初始化接口使用 `setup` JWT。
- 服务间 API 使用 `service` JWT，不允许浏览器前端调用。

### 3.2 通用响应

成功响应建议：

```json
{
  "request_id": "req_001",
  "data": {},
  "meta": {}
}
```

列表响应建议：

```json
{
  "request_id": "req_001",
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 20,
    "total": 120
  }
}
```

错误响应沿用公共错误结构：

```json
{
  "request_id": "req_001",
  "error_code": "PERM_DENIED",
  "message": "permission denied",
  "stage": "permission",
  "retryable": false,
  "details": {}
}
```

### 3.3 查询参数

列表接口统一支持：

- `page`
- `page_size`
- `sort`
- `order`
- `keyword`
- `status`
- `created_after`
- `created_before`

涉及租户隔离的接口必须从 JWT 和权限上下文解析 `enterprise_id`，禁止前端传入 `enterprise_id` 后直接信任。

### 3.4 前端禁止直连的能力

以下接口或能力不暴露给浏览器前端：

- Model Gateway 原始 embedding、rerank、chat API。
- Worker 内部任务领取 API。
- Qdrant、MinIO、Redis、PostgreSQL。
- `rag-admin setup-token issue`、`rag-admin setup-token rotate`。
- 物理删除索引、直接更新索引 payload、直接写权限快照。

## 4. 初始化 API

仅系统未初始化或进入恢复初始化流程时开放。

```http
GET  /internal/v1/setup-state
POST /internal/v1/setup-config-validations
PUT  /internal/v1/setup-initialization
```

说明：

- `GET /setup-state` 不需要 token，只返回有限初始化状态，不返回 setup token 明文。
- `POST /setup-config-validations` 创建一次初始化配置校验请求，不写入 active config。
- `PUT /setup-initialization` 以幂等语义提交初始化目标状态，校验通过后写入首个管理员、默认组织、默认角色和 `active_config v1`。
- setup JWT 由受控 CLI 或部署平台签发，每次签发都生成新 token，并使旧 token 失效。
- 初始化完成后，配置校验和初始化写接口必须关闭。

## 5. 认证、会话与当前用户 API

```http
POST   /internal/v1/sessions
DELETE /internal/v1/sessions/current
POST   /internal/v1/token-refreshes
GET    /internal/v1/users/me
PUT    /internal/v1/users/me/password
```

### 5.1 创建会话

`POST /internal/v1/sessions`

请求：

```json
{
  "username": "alice",
  "password": "********"
}
```

响应：

```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

### 5.2 刷新 token

`POST /internal/v1/token-refreshes`

要求：

- refresh JWT 通过 `Authorization: Bearer <refresh_jwt>` 传递，不使用 access JWT。
- refresh token 必须校验 `jti` 状态。
- 建议采用 refresh token rotation，签发新 refresh token 后将旧 refresh token 标记为 used 或 revoked。
- 刷新失败必须记录审计。

### 5.3 当前用户

`GET /internal/v1/users/me`

响应应包含账号基础信息、部门、角色摘要和可用于前端菜单控制的 scopes 摘要。完整权限上下文仍由 Permission Service 运行时构建，不能直接信任前端缓存。

## 6. 查询问答 API

```http
POST /internal/v1/queries
POST /internal/v1/query-streams
```

说明：

- `POST /queries` 创建一次非流式查询请求并返回答案。
- `POST /query-streams` 创建一次流式查询请求，响应使用 SSE。
- 严格引用模式下，不能输出未经答案引用有效性校验的最终 token。

请求示例：

```json
{
  "kb_ids": ["kb_sales", "kb_policy"],
  "query": "销售合同审批需要哪些材料？",
  "mode": "answer",
  "filters": {
    "updated_after": "2026-01-01",
    "source_type": ["policy", "faq"],
    "tags": ["合同"]
  },
  "top_k": 8,
  "include_sources": true
}
```

## 7. 普通知识库浏览 API

这些接口面向普通前端，返回当前用户可访问的知识库、文件夹和文档。

```http
GET /internal/v1/knowledge-bases
GET /internal/v1/knowledge-bases/{kb_id}
GET /internal/v1/knowledge-bases/{kb_id}/folders
GET /internal/v1/knowledge-bases/{kb_id}/documents
GET /internal/v1/documents/{doc_id}
GET /internal/v1/documents/{doc_id}/versions
GET /internal/v1/documents/{doc_id}/chunks
GET /internal/v1/documents/{doc_id}/preview
```

要求：

- 所有列表都必须经过 Permission Service 过滤。
- 普通用户只能看到自己有权访问的知识库、文件夹、文档和 chunk。
- `preview` 返回原文预览或解析后内容时必须做 access block 校验和引用有效性检查。
- 文档原文下载如后续支持，应使用短期签名 URL，并在签发前做权限校验和审计。

## 8. 文档导入与任务 API

普通用户或具备知识库管理权限的管理员可根据权限导入文档。

```http
POST  /internal/v1/knowledge-bases/{kb_id}/documents
POST  /internal/v1/knowledge-bases/{kb_id}/document-imports
GET   /internal/v1/import-jobs/{job_id}
PATCH /internal/v1/import-jobs/{job_id}
POST  /internal/v1/import-jobs/{job_id}/retries
```

说明：

- `POST /knowledge-bases/{kb_id}/documents` 用于上传单个或多个文件并创建文档导入任务，可使用 multipart/form-data。
- `POST /knowledge-bases/{kb_id}/document-imports` 用于通过 URL、连接器或批量元数据创建导入任务。
- 取消任务使用 `PATCH /import-jobs/{job_id}`，请求体设置 `status=cancelled`。
- 重试任务使用 `POST /import-jobs/{job_id}/retries`，表示创建一次重试请求。

管理后台任务列表：

```http
GET /internal/v1/admin/import-jobs
GET /internal/v1/admin/import-jobs/{job_id}
```

列表筛选建议：

- `status`
- `stage`
- `kb_id`
- `created_by`
- `created_after`
- `created_before`

## 9. 管理后台：知识库 API

```http
GET    /internal/v1/admin/knowledge-bases
POST   /internal/v1/admin/knowledge-bases
GET    /internal/v1/admin/knowledge-bases/{kb_id}
PATCH  /internal/v1/admin/knowledge-bases/{kb_id}
DELETE /internal/v1/admin/knowledge-bases/{kb_id}
```

创建请求示例：

```json
{
  "name": "销售知识库",
  "owner_department_id": "dept_sales",
  "default_visibility": "department",
  "config_scope_id": "cfg_scope_sales"
}
```

要求：

- 创建和修改必须校验 `knowledge_base:manage` 或等价 scope。
- 禁用、归档、恢复都使用 `PATCH` 修改 `status`，例如 `active`、`disabled`、`archived`。
- `DELETE` 表示删除或软删除知识库，必须先阻断查询可见性并记录审计。
- `default_visibility=enterprise` 属于扩大可见范围，应按配置触发审批或高风险审计。

## 10. 管理后台：文件夹 API

```http
GET    /internal/v1/admin/knowledge-bases/{kb_id}/folders
POST   /internal/v1/admin/knowledge-bases/{kb_id}/folders
GET    /internal/v1/admin/folders/{folder_id}
PATCH  /internal/v1/admin/folders/{folder_id}
DELETE /internal/v1/admin/folders/{folder_id}
```

说明：

- 移动文件夹使用 `PATCH /admin/folders/{folder_id}` 修改 `parent_id`。
- 归档文件夹使用 `PATCH` 修改 `status=archived`。

要求：

- 移动文件夹必须防止循环引用。
- 文件夹权限继承结果不得在查询时临时推导，权限策略变化必须形成资源策略版本和权限快照刷新任务。
- 文件夹归档不能导致 active 文档绕过查询过滤。

## 11. 管理后台：文档 API

```http
GET    /internal/v1/admin/knowledge-bases/{kb_id}/documents
GET    /internal/v1/admin/documents/{doc_id}
PATCH  /internal/v1/admin/documents/{doc_id}
DELETE /internal/v1/admin/documents/{doc_id}
POST   /internal/v1/admin/documents/{doc_id}/index-jobs
GET    /internal/v1/admin/documents/{doc_id}/versions
GET    /internal/v1/admin/documents/{doc_id}/chunks
GET    /internal/v1/admin/documents/{doc_id}/index-versions
```

可修改字段建议：

- `title`
- `folder_id`
- `tags`
- `owner_department_id`
- `visibility`
- `lifecycle_status`

要求：

- 修改 `owner_department_id` 或 `visibility` 必须调用 Permission Service，生成新的资源策略版本、权限快照，并触发索引 payload 刷新。
- 删除必须先写 access block，再异步物理删除索引。
- 恢复软删除文档使用 `PATCH` 修改 `lifecycle_status`，并按数据状态决定是否需要重建索引。
- 重建索引使用 `POST /admin/documents/{doc_id}/index-jobs` 创建新的索引任务。

## 12. 管理后台：用户 API

```http
GET    /internal/v1/admin/users
POST   /internal/v1/admin/users
GET    /internal/v1/admin/users/{user_id}
PATCH  /internal/v1/admin/users/{user_id}
DELETE /internal/v1/admin/users/{user_id}
PUT    /internal/v1/admin/users/{user_id}/password
DELETE /internal/v1/admin/users/{user_id}/lock
```

说明：

- 禁用用户使用 `PATCH /admin/users/{user_id}` 修改 `status=disabled`。
- 离职或软删除用户使用 `DELETE /admin/users/{user_id}`。
- 重置密码使用 `PUT /admin/users/{user_id}/password`。
- 解锁账号使用 `DELETE /admin/users/{user_id}/lock`。

要求：

- 用户创建由 Auth Service 负责账号生命周期。
- 默认角色绑定由 Permission Service 负责。
- 部门管理员只能在授权部门范围内创建或维护用户。
- 高风险账号操作必须审计。

## 13. 管理后台：组织 API

```http
GET    /internal/v1/admin/departments
POST   /internal/v1/admin/departments
GET    /internal/v1/admin/departments/{department_id}
PATCH  /internal/v1/admin/departments/{department_id}
DELETE /internal/v1/admin/departments/{department_id}

GET /internal/v1/admin/users/{user_id}/departments
PUT /internal/v1/admin/users/{user_id}/departments
```

后续接入外部组织源时补充：

```http
GET   /internal/v1/admin/org-sync-jobs
POST  /internal/v1/admin/org-sync-jobs
GET   /internal/v1/admin/org-sync-jobs/{job_id}
PATCH /internal/v1/admin/org-sync-jobs/{job_id}
```

说明：

- 禁用部门使用 `PATCH /admin/departments/{department_id}` 修改 `status=disabled`。
- 发布组织同步结果使用 `PATCH /admin/org-sync-jobs/{job_id}` 修改 `status=published`。

要求：

- 部门不建模上下级递归。
- 组织变更必须递增 `org_version`，并失效用户 subject 缓存和权限上下文缓存。

## 14. 管理后台：角色与权限 API

```http
GET    /internal/v1/admin/roles
POST   /internal/v1/admin/roles
GET    /internal/v1/admin/roles/{role_id}
PATCH  /internal/v1/admin/roles/{role_id}
DELETE /internal/v1/admin/roles/{role_id}

GET    /internal/v1/admin/users/{user_id}/role-bindings
POST   /internal/v1/admin/users/{user_id}/role-bindings
PUT    /internal/v1/admin/users/{user_id}/role-bindings
DELETE /internal/v1/admin/users/{user_id}/role-bindings/{binding_id}

GET /internal/v1/permission-evaluations
PUT /internal/v1/knowledge-bases/{kb_id}/permissions
PUT /internal/v1/documents/{doc_id}/permissions
```

`GET /internal/v1/permission-evaluations` 查询参数：

- `resource_type`
- `resource_id`
- `user_id`

说明：

- 禁用角色使用 `PATCH /admin/roles/{role_id}` 修改 `status=disabled`。
- 删除内置角色必须被拒绝；`DELETE` 只允许删除或归档非内置角色。
- `POST /role-bindings` 用于新增单个或多个角色绑定。
- `PUT /role-bindings` 用于整体替换某用户角色绑定集合。
- `DELETE /role-bindings/{binding_id}` 用于撤销某个角色绑定。

要求：

- 分配 `system_admin`、`security_admin` 等高风险角色必须触发高风险审计，生产阶段建议审批或双人确认。
- 文档权限只支持 `department` 和 `enterprise`。
- 权限收紧必须先阻断旧访问，再异步刷新索引 payload。

## 15. 管理后台：配置 API

```http
GET   /internal/v1/admin/configs
GET   /internal/v1/admin/configs/{key}
PUT   /internal/v1/admin/configs/{key}
GET   /internal/v1/admin/config-versions
GET   /internal/v1/admin/config-versions/{version}
PATCH /internal/v1/admin/config-versions/{version}
GET   /internal/v1/admin/config-version-diffs
POST  /internal/v1/admin/config-validations
POST  /internal/v1/admin/config-rollbacks
```

说明：

- 保存配置草稿使用 `PUT /admin/configs/{key}`。
- 发布配置版本使用 `PATCH /admin/config-versions/{version}` 修改 `status=active`。
- 回滚配置使用 `POST /admin/config-rollbacks` 创建一次回滚请求。
- 配置校验使用 `POST /admin/config-validations` 创建一次校验请求。
- 配置 diff 使用 `GET /admin/config-version-diffs?from=12&to=13`。

要求：

- 写接口只允许 system_admin 或 security_admin。
- 高风险配置必须审批。
- API 响应不得返回 secret value，只能返回 secret ref 和脱敏摘要。

## 16. 管理后台：审计与可观测 API

```http
GET /internal/v1/admin/audit-logs
GET /internal/v1/admin/audit-logs/{audit_id}
GET /internal/v1/admin/query-logs
GET /internal/v1/admin/query-logs/{query_log_id}
GET /internal/v1/admin/model-call-logs
GET /internal/v1/admin/metrics-summary
GET /internal/v1/admin/alerts
```

审计日志筛选建议：

- `actor_id`
- `action`
- `resource_type`
- `resource_id`
- `result`
- `risk_level`
- `created_after`
- `created_before`

查询日志筛选建议：

- `user_id`
- `kb_id`
- `status`
- `degraded`
- `config_version`
- `permission_version`
- `created_after`
- `created_before`

要求：

- audit_admin 可查看审计和评测记录，但默认不具备业务数据修改权限。
- 查询原文、完整 prompt、文档 snippet 是否展示必须服从审计配置和脱敏策略。
- 普通日志不作为管理后台直接数据源，管理后台读取受控审计表或指标聚合。

## 17. Healthcheck 与运维 API

```http
GET /health/live
GET /health/ready
```

说明：

- healthcheck 是运维约定接口，允许不采用 `/internal/v1` 前缀。
- `live` 只表示进程存活。
- `ready` 必须检查数据库连接、初始化状态、active config、ServiceBootstrap 状态和核心迁移版本。
- healthcheck 不返回 secret、内部拓扑和敏感配置。

以下能力建议通过 CLI 或受控运维入口，不直接开放给浏览器前端：

```text
rag-admin setup-token issue
rag-admin setup-token rotate
rag-admin config active
rag-admin config validate <file>
rag-admin import retry <job_id>
rag-admin index check <kb_id>
rag-admin permission refresh <resource_id>
rag-admin health check
```

## 18. 内部服务 API

Model Gateway 内部 API：

```http
POST /internal/v1/model-embeddings
POST /internal/v1/model-rerankings
POST /internal/v1/model-chat-completions
GET  /internal/v1/model-catalog
GET  /internal/v1/model-health
```

要求：

- 只能由后端服务或 Worker 使用 service JWT 调用。
- 不允许浏览器前端直接调用。
- 模型请求和响应必须脱敏，普通日志不得记录完整 prompt。

## 19. 前端菜单与权限映射

建议前端通过 `GET /internal/v1/users/me` 获取菜单所需的 scope 摘要，但后端仍必须在每个 API 上执行权限校验。

| 前端区域 | 典型 scope |
| --- | --- |
| 查询问答 | `rag:query` |
| 个人可见知识库 | `knowledge_base:read` |
| 文档导入 | `document:import` |
| 用户管理 | `user:manage` |
| 组织管理 | `org:manage` |
| 角色权限管理 | `role:manage`、`permission:manage` |
| 知识库管理 | `knowledge_base:manage` |
| 配置中心 | `config:manage` |
| 审计中心 | `audit:read` |

前端菜单隐藏不是安全边界。所有管理 API 都必须由 Auth Service 鉴别身份，再由 Permission Service 校验 scope 和资源作用域。
