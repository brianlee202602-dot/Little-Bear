# P0 数据库 Schema 设计

## 1. 文档目标

本文定义 Little Bear RAG 后端 P0 阶段的 PostgreSQL 业务事实源 Schema，作为后续 Alembic migration、Repository、权限矩阵、状态机、测试计划和正式编码的输入。

设计依据：

- `docs/MVP范围说明.md`
- `docs/contracts/config.schema.json`
- `docs/contracts/openapi.yaml`
- `docs/modules/14-核心数据模型设计实现文档.md`
- `docs/modules/01-初始化服务设计实现文档.md`
- `docs/modules/02-认证服务设计实现文档.md`
- `docs/modules/03-组织服务设计实现文档.md`
- `docs/modules/04-权限服务设计实现文档.md`
- `docs/modules/05-配置服务设计实现文档.md`
- `docs/modules/06-导入服务与工作进程设计实现文档.md`
- `docs/modules/07-索引服务设计实现文档.md`
- `docs/modules/11-审计与可观测性设计实现文档.md`

## 2. 总体原则

- PostgreSQL 是业务事实源。Qdrant、关键词索引、Redis 缓存和对象存储都是派生数据或外部存储。
- P0 使用单企业模型，但所有租户业务表仍保留 `enterprise_id`，避免后续扩展时重构主键和索引。
- 全局表必须明确 scope，不假装属于某个企业。
- 文档、chunk、权限快照、索引版本和引用必须可对账。
- draft、deleted、blocked、权限版本落后的数据必须 fail closed，不允许进入查询上下文。
- 软删除必须有 `deleted_at` 或 access block，不依赖物理删除保证安全。
- 所有写入链路必须能记录审计事件或关联审计事件。

## 3. 通用类型约定

| 类型 | PostgreSQL 类型 | 说明 |
| --- | --- | --- |
| ID | `uuid` | 由应用生成 UUIDv7 或等价有序 UUID |
| 时间 | `timestamptz` | 统一 UTC 存储 |
| JSON | `jsonb` | 配置、payload、摘要、扩展字段 |
| hash | `text` | sha256 hex 或等价稳定 hash |
| 状态 | `text` + CHECK 或 enum | P0 建议使用 CHECK，方便 migration 调整 |
| 金额/分数 | `numeric` 或 `double precision` | 检索分数用 `double precision` |
| 大文本 | object key + preview | 原文和大 chunk 不直接放普通日志或审计摘要 |

通用字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `uuid primary key` | 主键 |
| `enterprise_id` | `uuid not null` | 租户隔离字段，global 表除外 |
| `created_at` | `timestamptz not null default now()` | 创建时间 |
| `updated_at` | `timestamptz not null default now()` | 更新时间 |
| `deleted_at` | `timestamptz null` | 软删除时间，按表需要添加 |
| `created_by` | `uuid null` | 操作者用户 ID，初始化或系统任务可为空 |
| `updated_by` | `uuid null` | 最近修改者 |

## 4. 枚举清单

建议首批 migration 使用 CHECK 约束定义枚举范围：

| 枚举 | 值 |
| --- | --- |
| `setup_status` | `not_initialized`、`setup_required`、`validating_config`、`testing_dependencies`、`creating_admin`、`publishing_config`、`initialized`、`validation_failed`、`dependency_test_failed`、`initialization_failed`、`recovery_required`、`recovery_validating_config`、`recovery_publishing_config` |
| `token_type` | `access`、`refresh`、`service`、`setup` |
| `token_status` | `active`、`used`、`revoked`、`expired` |
| `secret_status` | `active`、`rotating`、`revoked`、`deleted` |
| `config_status` | `draft`、`validating`、`active`、`archived`、`failed` |
| `enterprise_status` | `active`、`disabled`、`deleted` |
| `department_status` | `active`、`disabled`、`deleted` |
| `user_status` | `active`、`disabled`、`locked`、`deleted` |
| `membership_status` | `active`、`deleted` |
| `role_status` | `active`、`disabled`、`archived` |
| `role_binding_status` | `active`、`revoked` |
| `role_scope_type` | `enterprise`、`department`、`knowledge_base` |
| `resource_type` | `enterprise`、`department`、`user`、`role`、`role_binding`、`permission`、`knowledge_base`、`folder`、`document`、`chunk`、`import_job`、`config`、`query`、`setup`、`model_call` |
| `policy_status` | `draft`、`active`、`archived` |
| `visibility` | `department`、`enterprise` |
| `kb_status` | `active`、`disabled`、`archived`、`deleted` |
| `folder_status` | `active`、`disabled`、`archived`、`deleted` |
| `document_source_type` | `upload`、`api`、`connector`、`manual` |
| `document_lifecycle_status` | `draft`、`active`、`archived`、`deleted` |
| `document_index_status` | `none`、`indexing`、`indexed`、`index_failed`、`blocked` |
| `document_version_status` | `draft`、`parsed`、`chunked`、`indexed`、`active`、`archived`、`failed` |
| `chunk_status` | `draft`、`active`、`archived`、`deleted` |
| `index_version_status` | `draft`、`ready`、`active`、`archived`、`pending_delete`、`failed` |
| `chunk_visibility_state` | `draft`、`active`、`blocked`、`deleted` |
| `access_block_reason` | `deleted`、`permission_tightened`、`legal_hold`、`security_incident` |
| `block_level` | `query`、`citation`、`all` |
| `access_block_status` | `active`、`released` |
| `import_job_type` | `upload`、`url`、`metadata_batch`、`index_rebuild`、`permission_refresh`、`index_delete` |
| `import_job_status` | `queued`、`running`、`retrying`、`partial_success`、`success`、`failed`、`cancelled` |
| `import_job_stage` | `validate`、`parse`、`clean`、`chunk`、`embed`、`index`、`publish`、`cleanup`、`finished` |
| `audit_result` | `success`、`failure`、`denied` |
| `risk_level` | `low`、`medium`、`high`、`critical` |
| `query_status` | `success`、`failed`、`denied` |
| `model_call_status` | `success`、`failed`、`degraded` |
| `cache_entry_type` | `query_embedding`、`retrieval_result`、`final_answer` |

## 5. 初始化、配置与 Secret

### 5.1 `system_state`

用途：保存全局初始化状态、active config 指针和全局控制状态。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `key` | `text` | 否 | PK | 状态键 |
| `value_json` | `jsonb` | 否 |  | 状态值 |
| `updated_at` | `timestamptz` | 否 | idx | 更新时间 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 操作者 |

P0 必需 key：

| key | value_json 说明 |
| --- | --- |
| `setup_status` | `{"status":"not_initialized|setup_required|validating_config|testing_dependencies|creating_admin|publishing_config|initialized|validation_failed|dependency_test_failed|initialization_failed|recovery_required|recovery_validating_config|recovery_publishing_config"}` |
| `initialized` | `{"value":true|false}` |
| `active_config_version` | `{"version":1}` |
| `permission_version` | `{"version":1}` |
| `schema_migration_version` | `{"version":"0001"}` |
| `recovery_setup_allowed` | `{"value":true|false}` |
| `recovery_reason` | `{"reason":"active_config_missing|config_corrupted|bootstrap_failed|null"}` |
| `setup_attempt_count` | `{"count":0}` |
| `setup_locked_until` | `{"until":"2026-05-01T00:00:00Z|null"}` |

约束：

- `system_state` 是 global 表，不带 `enterprise_id`。
- 修改 `active_config_version` 必须在配置发布事务内完成。

### 5.2 `setup_tokens`

用途：记录 setup JWT 签发、失效和一次性使用状态。每次签发新 setup JWT 时，必须在同一事务内失效旧的 active setup token。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | setup token 记录 ID |
| `jwt_jti` | `text` | 否 | UNIQUE, FK `jwt_tokens.jti` | JWT jti |
| `token_hash` | `text` | 否 | UNIQUE | token 明文 hash，不存明文 |
| `status` | `text` | 否 | idx, CHECK `token_status` | `active`、`used`、`revoked`、`expired` |
| `scopes` | `text[]` | 否 | GIN | P0 必须包含 `setup:validate` 和 `setup:initialize` |
| `issued_by` | `uuid` | 是 | FK `users.id` | CLI 或恢复初始化可能为空 |
| `issued_at` | `timestamptz` | 否 | idx | 签发时间 |
| `expires_at` | `timestamptz` | 否 | idx | 过期时间 |
| `used_at` | `timestamptz` | 是 |  | 使用时间 |
| `revoked_at` | `timestamptz` | 是 |  | 失效时间 |
| `revoked_reason` | `text` | 是 |  | 失效原因 |

索引：

- `idx_setup_tokens_status_expires(status, expires_at)`
- `uq_setup_tokens_one_active`：partial unique，`status='active'` 时最多一条。

约束：

- 签发新 setup JWT 前必须在同一事务内将旧的 active setup token 标记为 `revoked`。
- `scopes` 必须包含 `setup:validate` 和 `setup:initialize`，不得授予普通业务或管理后台 scope。

### 5.3 `config_versions`

用途：保存配置版本元数据和发布状态。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 配置版本 ID |
| `version` | `integer` | 否 | UNIQUE | 递增版本号，初始化为 1 |
| `scope_type` | `text` | 否 | idx | P0 固定 `global` |
| `scope_id` | `text` | 否 | idx | P0 固定 `global` |
| `status` | `text` | 否 | idx, CHECK `config_status` | draft/validating/active/archived/failed |
| `config_hash` | `text` | 否 | UNIQUE | active config bundle hash |
| `schema_version` | `integer` | 否 |  | P0 固定 1 |
| `validation_result_json` | `jsonb` | 是 |  | 校验结果摘要 |
| `risk_level` | `text` | 否 | CHECK `risk_level` | 配置风险等级 |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |
| `activated_at` | `timestamptz` | 是 | idx | 发布时间 |

索引：

- `uq_config_versions_one_active`：partial unique，`status='active'` 时最多一条。
- `idx_config_versions_status_created(status, created_at desc)`

### 5.4 `system_configs`

用途：保存配置版本下的配置项。P0 使用 global scope 和 `docs/contracts/config.schema.json` 的顶层配置 key。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 配置项 ID |
| `config_version_id` | `uuid` | 否 | FK `config_versions.id` | 所属配置版本 |
| `version` | `integer` | 否 | idx | 冗余版本号，便于查询 |
| `scope_type` | `text` | 否 | idx | P0 固定 `global` |
| `scope_id` | `text` | 否 | idx | P0 固定 `global` |
| `key` | `text` | 否 | idx | 如 `redis`、`storage`、`model_gateway` |
| `value_json` | `jsonb` | 否 | GIN | 配置值，不得含 secret value |
| `value_hash` | `text` | 否 | idx | 配置值 hash |
| `status` | `text` | 否 | idx, CHECK `config_status` | 与版本状态一致或 draft |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |

唯一约束：

- `uq_system_configs_version_key(config_version_id, key)`
- `uq_system_configs_scope_version_key(scope_type, scope_id, version, key)`

### 5.5 `secrets`

用途：P0 Secret Store，保存加密后的敏感值。active config 只保存 Secret ref。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | Secret ID |
| `scope_type` | `text` | 否 | idx | P0 默认 `global` |
| `scope_id` | `text` | 否 | idx | P0 默认 `global` |
| `secret_ref` | `text` | 否 | UNIQUE | 例如 `secret://rag/auth/jwt-signing-key` |
| `ciphertext` | `bytea` | 否 |  | 加密密文 |
| `encryption_meta_json` | `jsonb` | 否 |  | 算法、key id、nonce 等 |
| `value_hash` | `text` | 否 | idx | 明文 hash，用于变更检测，不可逆 |
| `status` | `text` | 否 | idx, CHECK `secret_status` | active/rotating/revoked/deleted |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `rotated_at` | `timestamptz` | 是 |  | 最近轮换时间 |

约束：

- API 响应和普通日志不得返回 `ciphertext` 或 secret 明文。
- `secret_ref` 必须匹配 `docs/contracts/config.schema.json` 中 SecretRef 格式。

## 6. 认证、组织与权限

### 6.1 `enterprises`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 企业 ID |
| `code` | `text` | 否 | UNIQUE | 企业编码，P0 初始化固定一个 |
| `name` | `text` | 否 |  | 企业名称 |
| `status` | `text` | 否 | idx, CHECK `enterprise_status` | active/disabled/deleted |
| `org_version` | `integer` | 否 | idx | 组织版本，默认 1 |
| `permission_version` | `integer` | 否 | idx | 权限版本，默认 1 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 |  | 软删除时间 |

### 6.2 `users`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 用户 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `username` | `text` | 否 |  | 登录名 |
| `display_name` | `text` | 否 |  | 显示名 |
| `email` | `text` | 是 | idx | 邮箱 |
| `phone` | `text` | 是 |  | 手机号 |
| `status` | `text` | 否 | idx, CHECK `user_status` | active/disabled/locked/deleted |
| `last_login_at` | `timestamptz` | 是 |  | 最近登录 |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 | idx | 软删除时间 |

唯一约束：

- `uq_users_enterprise_username(enterprise_id, lower(username))`
- `uq_users_enterprise_email(enterprise_id, lower(email))`，partial，`email is not null and deleted_at is null`

### 6.3 `user_credentials`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `user_id` | `uuid` | 否 | PK, FK `users.id` | 用户 ID |
| `password_hash` | `text` | 否 |  | 密码 hash |
| `password_alg` | `text` | 否 |  | argon2id/bcrypt 等 |
| `password_updated_at` | `timestamptz` | 否 |  | 最近改密时间 |
| `force_change_password` | `boolean` | 否 |  | 是否强制改密 |
| `failed_login_count` | `integer` | 否 |  | 失败次数 |
| `locked_until` | `timestamptz` | 是 | idx | 锁定到期 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |

约束：

- 密码明文只允许存在于请求生命周期。
- 重置密码必须写审计并可设置 `force_change_password=true`。

### 6.4 `jwt_tokens`

用途：保存 JWT jti 状态，用于吊销、refresh rotation、setup JWT 失效和审计。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `jti` | `text` | 否 | PK | JWT ID |
| `enterprise_id` | `uuid` | 是 | FK `enterprises.id`, idx | setup/service 可为空 |
| `subject_user_id` | `uuid` | 是 | FK `users.id`, idx | 普通用户 token |
| `service_name` | `text` | 是 | idx | service token |
| `token_type` | `text` | 否 | idx, CHECK `token_type` | access/refresh/service/setup |
| `status` | `text` | 否 | idx, CHECK `token_status` | active/used/revoked/expired |
| `scopes` | `text[]` | 否 | GIN | token scopes 摘要 |
| `issued_at` | `timestamptz` | 否 | idx | 签发时间 |
| `expires_at` | `timestamptz` | 否 | idx | 过期时间 |
| `used_at` | `timestamptz` | 是 |  | refresh/setup 一次性使用时间 |
| `revoked_at` | `timestamptz` | 是 |  | 吊销时间 |
| `replaced_by_jti` | `text` | 是 | FK `jwt_tokens.jti` | refresh rotation 后的新 jti |
| `metadata_json` | `jsonb` | 是 |  | user agent、IP hash 等摘要 |

索引：

- `idx_jwt_tokens_subject_status(subject_user_id, token_type, status)`
- `idx_jwt_tokens_expires(status, expires_at)`

### 6.5 `departments`

P0 部门不建模上下级递归。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 部门 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `code` | `text` | 否 |  | 部门编码 |
| `name` | `text` | 否 | idx | 部门名称 |
| `status` | `text` | 否 | idx, CHECK `department_status` | active/disabled/deleted |
| `is_default` | `boolean` | 否 | idx | 是否默认部门 |
| `org_version` | `integer` | 否 | idx | 组织版本 |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 |  | 软删除时间 |

唯一约束：

- `uq_departments_enterprise_code(enterprise_id, code)`
- `uq_departments_one_default(enterprise_id)`，partial，`is_default=true and status='active'`

### 6.6 `user_department_memberships`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 关系 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `user_id` | `uuid` | 否 | FK `users.id`, idx | 用户 ID |
| `department_id` | `uuid` | 否 | FK `departments.id`, idx | 部门 ID |
| `is_primary` | `boolean` | 否 | idx | 是否主部门 |
| `status` | `text` | 否 | idx, CHECK `membership_status` | active/deleted |
| `created_by` | `uuid` | 是 | FK `users.id` | 操作者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `deleted_at` | `timestamptz` | 是 |  | 删除时间 |

唯一约束：

- `uq_user_dept_active(enterprise_id, user_id, department_id)`，partial，`status='active'`
- `uq_user_primary_dept(enterprise_id, user_id)`，partial，`is_primary=true and status='active'`

### 6.7 `roles`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 角色 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `code` | `text` | 否 |  | 角色编码 |
| `name` | `text` | 否 |  | 角色名称 |
| `scope_type` | `text` | 否 | CHECK `role_scope_type` | enterprise/department/knowledge_base |
| `scopes` | `text[]` | 否 | GIN | 权限 scope 列表 |
| `is_builtin` | `boolean` | 否 | idx | 是否内置角色 |
| `status` | `text` | 否 | idx, CHECK `role_status` | active/disabled/archived |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |

唯一约束：

- `uq_roles_enterprise_code(enterprise_id, code)`

P0 内置角色：

- `system_admin`
- `security_admin`
- `audit_admin`
- `department_admin`
- `knowledge_base_admin`
- `employee`

### 6.8 `role_bindings`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 绑定 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `user_id` | `uuid` | 否 | FK `users.id`, idx | 用户 ID |
| `role_id` | `uuid` | 否 | FK `roles.id`, idx | 角色 ID |
| `scope_type` | `text` | 否 | CHECK `role_scope_type` | 绑定作用域类型 |
| `scope_id` | `uuid` | 是 | idx | department/kb 级绑定的资源 ID |
| `status` | `text` | 否 | idx, CHECK `role_binding_status` | active/revoked |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `revoked_by` | `uuid` | 是 | FK `users.id` | 撤销者 |
| `revoked_at` | `timestamptz` | 是 |  | 撤销时间 |

唯一约束：

- `uq_role_bindings_active_enterprise(enterprise_id, user_id, role_id, scope_type)`，partial，`status='active' and scope_type='enterprise' and scope_id is null`
- `uq_role_bindings_active_scoped(enterprise_id, user_id, role_id, scope_type, scope_id)`，partial，`status='active' and scope_id is not null`

约束：

- 变更 active 绑定必须递增 `enterprises.permission_version`。
- 高风险角色绑定必须写审计。
- `scope_type='enterprise'` 时 `scope_id` 必须为空；`scope_type in ('department','knowledge_base')` 时 `scope_id` 必须非空。

### 6.9 `resource_policies`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 策略 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `resource_type` | `text` | 否 | idx, CHECK `resource_type` | 资源类型 |
| `resource_id` | `uuid` | 否 | idx | 资源 ID |
| `version` | `integer` | 否 | idx | 资源策略版本 |
| `policy_json` | `jsonb` | 否 | GIN | 策略内容 |
| `policy_hash` | `text` | 否 | idx | 策略 hash |
| `status` | `text` | 否 | idx, CHECK `policy_status` | draft/active/archived |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `archived_at` | `timestamptz` | 是 |  | 归档时间 |

唯一约束：

- `uq_resource_policies_version(enterprise_id, resource_type, resource_id, version)`
- `uq_resource_policies_active(enterprise_id, resource_type, resource_id)`，partial，`status='active'`

### 6.10 `permission_snapshots`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 权限快照 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `resource_type` | `text` | 否 | idx | P0 主要 document/chunk |
| `resource_id` | `uuid` | 否 | idx | 资源 ID |
| `permission_version` | `integer` | 否 | idx | 全局权限版本 |
| `policy_id` | `uuid` | 是 | FK `resource_policies.id` | 资源策略 |
| `policy_version` | `integer` | 否 | idx | 资源策略版本 |
| `payload_json` | `jsonb` | 否 | GIN | 写入索引的权限 payload |
| `payload_hash` | `text` | 否 | idx | payload hash |
| `owner_department_id` | `uuid` | 否 | FK `departments.id`, idx | 文档归属部门 |
| `visibility` | `text` | 否 | idx, CHECK `visibility` | department/enterprise |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |

索引：

- `idx_permission_snapshots_resource(enterprise_id, resource_type, resource_id, permission_version desc)`
- `idx_permission_snapshots_filter(enterprise_id, visibility, owner_department_id)`

## 7. 知识库、文档与索引

### 7.1 `knowledge_bases`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 知识库 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `name` | `text` | 否 | idx | 名称 |
| `status` | `text` | 否 | idx, CHECK `kb_status` | active/disabled/archived/deleted |
| `owner_department_id` | `uuid` | 否 | FK `departments.id`, idx | 归属部门 |
| `default_visibility` | `text` | 否 | CHECK `visibility` | 默认可见性 |
| `policy_version` | `integer` | 否 | idx | 当前策略版本 |
| `config_scope_id` | `text` | 是 | idx | P0 可为空 |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 | idx | 删除时间 |

索引：

- `idx_kb_enterprise_status(enterprise_id, status)`
- `idx_kb_owner_visibility(enterprise_id, owner_department_id, default_visibility)`

### 7.2 `folders`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 文件夹 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `kb_id` | `uuid` | 否 | FK `knowledge_bases.id`, idx | 知识库 ID |
| `parent_id` | `uuid` | 是 | FK `folders.id`, idx | 父文件夹 |
| `name` | `text` | 否 | idx | 名称 |
| `path` | `text` | 否 | idx | 层级路径 |
| `policy_inherit_mode` | `text` | 否 |  | P0 默认 `inherit` |
| `status` | `text` | 否 | idx, CHECK `folder_status` | active/disabled/archived/deleted |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 |  | 删除时间 |

唯一约束：

- `uq_folders_root_name(enterprise_id, kb_id, lower(name))`，partial，`parent_id is null and deleted_at is null`
- `uq_folders_child_name(enterprise_id, kb_id, parent_id, lower(name))`，partial，`parent_id is not null and deleted_at is null`

约束：

- 文件夹循环引用由 service policy 校验，数据库用 FK 防止孤儿引用。

### 7.3 `documents`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 文档 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `kb_id` | `uuid` | 否 | FK `knowledge_bases.id`, idx | 知识库 ID |
| `folder_id` | `uuid` | 是 | FK `folders.id`, idx | 文件夹 ID |
| `title` | `text` | 否 | idx | 标题 |
| `source_type` | `text` | 否 | CHECK `document_source_type` | 来源类型 |
| `source_uri` | `text` | 是 |  | 原始来源 URI |
| `current_version_id` | `uuid` | 是 | FK `document_versions.id` | 当前 active 版本 |
| `lifecycle_status` | `text` | 否 | idx, CHECK `document_lifecycle_status` | draft/active/archived/deleted |
| `index_status` | `text` | 否 | idx, CHECK `document_index_status` | none/indexing/indexed/index_failed/blocked |
| `owner_department_id` | `uuid` | 否 | FK `departments.id`, idx | 归属部门 |
| `visibility` | `text` | 否 | idx, CHECK `visibility` | department/enterprise |
| `content_hash` | `text` | 是 | idx | 当前内容 hash |
| `permission_snapshot_id` | `uuid` | 是 | FK `permission_snapshots.id`, idx | 当前权限快照 |
| `tags` | `text[]` | 否 | GIN | 标签 |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `updated_by` | `uuid` | 是 | FK `users.id` | 更新者 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 | idx | 软删除时间 |

索引：

- `idx_documents_query_visible(enterprise_id, kb_id, lifecycle_status, index_status, visibility, owner_department_id)`
- `idx_documents_folder(enterprise_id, kb_id, folder_id, lifecycle_status)`
- `idx_documents_content_hash(enterprise_id, content_hash)`

约束：

- 查询只允许 `lifecycle_status='active' and index_status='indexed'`。
- 删除必须先写 `access_blocks`，再写 deleted 状态。

### 7.4 `document_versions`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 文档版本 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `document_id` | `uuid` | 否 | FK `documents.id`, idx | 文档 ID |
| `version_no` | `integer` | 否 | idx | 文档内递增版本号 |
| `object_key` | `text` | 是 |  | 原始文件对象 key |
| `parsed_object_key` | `text` | 是 |  | 解析结果 key |
| `cleaned_object_key` | `text` | 是 |  | 清洗结果 key |
| `parser_version` | `text` | 是 |  | 解析器版本 |
| `chunker_version` | `text` | 是 |  | 切块器版本 |
| `content_hash` | `text` | 否 | idx | 内容 hash |
| `status` | `text` | 否 | idx, CHECK `document_version_status` | draft/parsed/chunked/indexed/active/archived/failed |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |
| `activated_at` | `timestamptz` | 是 | idx | 激活时间 |

唯一约束：

- `uq_document_versions_no(enterprise_id, document_id, version_no)`
- `uq_document_versions_active(enterprise_id, document_id)`，partial，`status='active'`

### 7.5 `chunks`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | chunk ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `kb_id` | `uuid` | 否 | FK `knowledge_bases.id`, idx | 知识库 ID |
| `document_id` | `uuid` | 否 | FK `documents.id`, idx | 文档 ID |
| `document_version_id` | `uuid` | 否 | FK `document_versions.id`, idx | 文档版本 ID |
| `ordinal` | `integer` | 否 | idx | 文档内序号 |
| `text_object_key` | `text` | 是 |  | 大文本对象 key |
| `text_preview` | `text` | 否 |  | 限长预览 |
| `heading_path` | `text` | 是 |  | 标题路径 |
| `page_start` | `integer` | 是 |  | 起始页 |
| `page_end` | `integer` | 是 |  | 结束页 |
| `source_offsets` | `jsonb` | 是 |  | 原文偏移 |
| `content_hash` | `text` | 否 | idx | chunk hash |
| `token_count` | `integer` | 否 |  | token 数 |
| `quality_flags` | `text[]` | 否 | GIN | OCR、表格等标记 |
| `status` | `text` | 否 | idx, CHECK `chunk_status` | draft/active/archived/deleted |
| `permission_snapshot_id` | `uuid` | 是 | FK `permission_snapshots.id`, idx | 权限快照 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |
| `deleted_at` | `timestamptz` | 是 |  | 删除时间 |

唯一约束：

- `uq_chunks_version_ordinal(enterprise_id, document_version_id, ordinal)`

索引：

- `idx_chunks_active_doc(enterprise_id, document_id, document_version_id, status)`

### 7.6 `index_versions`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 索引版本 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `kb_id` | `uuid` | 否 | FK `knowledge_bases.id`, idx | 知识库 ID |
| `document_id` | `uuid` | 否 | FK `documents.id`, idx | 文档 ID |
| `document_version_id` | `uuid` | 否 | FK `document_versions.id`, idx | 文档版本 ID |
| `embedding_model` | `text` | 否 | idx | embedding 模型 |
| `model_version` | `text` | 否 | idx | 模型版本 |
| `dimension` | `integer` | 否 |  | 向量维度 |
| `collection_name` | `text` | 否 | idx | Qdrant collection |
| `status` | `text` | 否 | idx, CHECK `index_version_status` | draft/ready/active/archived/pending_delete/failed |
| `chunk_count` | `integer` | 否 |  | chunk 数 |
| `permission_snapshot_hash` | `text` | 否 | idx | 权限快照摘要 |
| `payload_hash` | `text` | 否 | idx | 索引 payload hash |
| `created_by` | `uuid` | 是 | FK `users.id` | 创建者 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |
| `activated_at` | `timestamptz` | 是 | idx | 激活时间 |

唯一约束：

- `uq_index_versions_active_doc(enterprise_id, document_id)`，partial，`status='active'`

### 7.7 `chunk_index_refs`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 索引引用 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `chunk_id` | `uuid` | 否 | FK `chunks.id`, idx | chunk ID |
| `index_version_id` | `uuid` | 否 | FK `index_versions.id`, idx | 索引版本 ID |
| `vector_id` | `text` | 否 | UNIQUE | Qdrant point ID |
| `keyword_id` | `uuid` | 是 | FK `keyword_index_entries.id` | 关键词索引 ID |
| `visibility_state` | `text` | 否 | idx, CHECK `chunk_visibility_state` | draft/active/blocked/deleted |
| `indexed_permission_version` | `integer` | 否 | idx | 写入索引时权限版本 |
| `payload_hash` | `text` | 否 | idx | payload hash |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |

索引：

- `idx_chunk_index_refs_visible(index_version_id, visibility_state, indexed_permission_version)`
- `idx_chunk_index_refs_chunk(chunk_id, visibility_state)`

约束：

- 查询只允许 `visibility_state='active'`。
- 权限收紧和删除必须先改为 `blocked`，再异步物理删除。

### 7.8 `keyword_index_entries`

用途：P0 PostgreSQL Full Text 派生索引表，支持关键词召回和与 `chunk_index_refs.keyword_id` 对账。

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 关键词索引 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `chunk_id` | `uuid` | 否 | FK `chunks.id`, idx | chunk ID |
| `document_id` | `uuid` | 否 | FK `documents.id`, idx | 文档 ID |
| `index_version_id` | `uuid` | 否 | FK `index_versions.id`, idx | 索引版本 |
| `search_text` | `text` | 否 |  | 检索文本 |
| `search_tsv` | `tsvector` | 否 | GIN | 关键词检索向量 |
| `owner_department_id` | `uuid` | 否 | FK `departments.id`, idx | 权限过滤字段 |
| `visibility` | `text` | 否 | idx, CHECK `visibility` | 权限过滤字段 |
| `visibility_state` | `text` | 否 | idx, CHECK `chunk_visibility_state` | draft/active/blocked/deleted |
| `indexed_permission_version` | `integer` | 否 | idx | 权限版本 |
| `payload_hash` | `text` | 否 | idx | payload hash |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `updated_at` | `timestamptz` | 否 |  | 更新时间 |

索引：

- `idx_keyword_entries_search`：GIN `search_tsv`
- `idx_keyword_entries_permission(enterprise_id, visibility, owner_department_id, visibility_state)`
- `idx_keyword_entries_index_version(index_version_id, visibility_state)`

## 8. 导入任务、阻断与缓存

### 8.1 `import_jobs`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 任务 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `job_type` | `text` | 否 | idx, CHECK `import_job_type` | upload/url/metadata_batch/index_rebuild 等 |
| `kb_id` | `uuid` | 是 | FK `knowledge_bases.id`, idx | 知识库 |
| `document_id` | `uuid` | 是 | FK `documents.id`, idx | 单文档任务 |
| `document_version_id` | `uuid` | 是 | FK `document_versions.id`, idx | 文档版本 |
| `status` | `text` | 否 | idx, CHECK `import_job_status` | queued/running/retrying/partial_success/success/failed/cancelled |
| `stage` | `text` | 否 | idx, CHECK `import_job_stage` | validate/parse/clean/chunk/embed/index/publish/cleanup/finished |
| `request_json` | `jsonb` | 否 |  | 请求摘要，不含 secret |
| `result_json` | `jsonb` | 是 |  | 结果摘要 |
| `error_code` | `text` | 是 | idx | 错误码 |
| `error_message` | `text` | 是 |  | 脱敏错误信息 |
| `idempotency_key` | `text` | 是 | idx | 幂等键 |
| `attempt_count` | `integer` | 否 |  | 尝试次数 |
| `max_attempts` | `integer` | 否 |  | 最大尝试次数 |
| `locked_by` | `text` | 是 | idx | Worker ID |
| `locked_until` | `timestamptz` | 是 | idx | 锁过期时间 |
| `next_retry_at` | `timestamptz` | 是 | idx | 下次重试时间 |
| `cancel_requested_at` | `timestamptz` | 是 | idx | 运行中任务取消请求时间；由 Worker 在阶段边界确认 |
| `cancel_requested_by` | `uuid` | 是 | FK `users.id`, idx | 发起取消的用户；系统任务可为空 |
| `created_by` | `uuid` | 是 | FK `users.id`, idx | 创建者 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |
| `updated_at` | `timestamptz` | 否 | idx | 更新时间 |
| `finished_at` | `timestamptz` | 是 | idx | 完成时间 |

唯一约束：

- `uq_import_jobs_idempotency(enterprise_id, coalesce(created_by::text, 'system'), idempotency_key)`，partial expression unique，`idempotency_key is not null`

索引：

- `idx_import_jobs_claim(status, next_retry_at, locked_until, created_at)`
- `idx_import_jobs_admin(enterprise_id, status, stage, created_at desc)`

### 8.2 `access_blocks`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 阻断 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `resource_type` | `text` | 否 | idx, CHECK `resource_type` | knowledge_base/document/chunk |
| `resource_id` | `uuid` | 否 | idx | 资源 ID |
| `reason` | `text` | 否 | idx, CHECK `access_block_reason` | deleted/permission_tightened 等 |
| `block_level` | `text` | 否 | idx, CHECK `block_level` | query/citation/all |
| `status` | `text` | 否 | idx, CHECK `access_block_status` | active/released |
| `created_by` | `uuid` | 是 | FK `users.id` | 操作者 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |
| `expires_at` | `timestamptz` | 是 | idx | 过期时间 |
| `released_at` | `timestamptz` | 是 |  | 释放时间 |
| `metadata_json` | `jsonb` | 是 |  | 摘要 |

索引：

- `idx_access_blocks_active(enterprise_id, resource_type, resource_id, status, expires_at)`

约束：

- 删除和权限收紧必须先写 active access block。
- 查询和 citation 校验必须检查 active access block。

### 8.3 `query_cache_entries`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `cache_key` | `text` | 否 | PK | 完整缓存 key hash |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `user_id` | `uuid` | 是 | FK `users.id`, idx | 最终答案缓存默认按用户隔离 |
| `entry_type` | `text` | 否 | idx, CHECK `cache_entry_type` | query_embedding/retrieval_result/final_answer |
| `permission_filter_hash` | `text` | 否 | idx | 权限过滤 hash |
| `request_filter_hash` | `text` | 否 | idx | 请求过滤 hash |
| `kb_ids_hash` | `text` | 否 | idx | 知识库集合 hash |
| `query_hash` | `text` | 否 | idx | query hash |
| `config_version` | `integer` | 否 | idx | 配置版本 |
| `permission_version` | `integer` | 否 | idx | 权限版本 |
| `index_version_hash` | `text` | 否 | idx | active index 版本集合 hash |
| `model_route_hash` | `text` | 否 | idx | 模型路由 hash |
| `prompt_template_version` | `text` | 是 | idx | Prompt 版本 |
| `value_json` | `jsonb` | 否 |  | 缓存值，不含敏感明文 |
| `created_at` | `timestamptz` | 否 |  | 创建时间 |
| `expires_at` | `timestamptz` | 否 | idx | 过期时间 |

约束：

- P0 `final_answer` 缓存默认关闭；若后续启用，必须 `user_id is not null`。
- 缓存命中后仍需轻量 access block 和 citation 校验。

## 9. 审计与可观测

### 9.1 `audit_logs`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 审计 ID |
| `enterprise_id` | `uuid` | 是 | FK `enterprises.id`, idx | setup/global 可为空 |
| `request_id` | `text` | 是 | idx | 请求 ID |
| `trace_id` | `text` | 是 | idx | Trace ID |
| `event_name` | `text` | 否 | idx | 事件名 |
| `actor_type` | `text` | 否 | idx | anonymous/setup/user/service/system |
| `actor_id` | `text` | 是 | idx | 用户 ID、服务名或 setup jti |
| `resource_type` | `text` | 否 | idx, CHECK `resource_type` | 资源类型 |
| `resource_id` | `text` | 是 | idx | 资源 ID |
| `action` | `text` | 否 | idx | 动作 |
| `result` | `text` | 否 | idx, CHECK `audit_result` | success/failure/denied |
| `risk_level` | `text` | 否 | idx, CHECK `risk_level` | low/medium/high/critical |
| `config_version` | `integer` | 是 | idx | 事件发生时的配置版本，setup 早期可为空 |
| `permission_version` | `integer` | 是 | idx | 事件发生时的权限版本，setup/global 事件可为空 |
| `index_version_hash` | `text` | 是 | idx | 涉及查询、导入、索引发布时的索引版本集合摘要 |
| `summary_json` | `jsonb` | 否 | GIN | 脱敏摘要 |
| `error_code` | `text` | 是 | idx | 错误码 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |

索引：

- `idx_audit_logs_admin(enterprise_id, event_name, result, risk_level, created_at desc)`
- `idx_audit_logs_resource(enterprise_id, resource_type, resource_id, created_at desc)`
- `idx_audit_logs_config_permission(enterprise_id, config_version, permission_version, created_at desc)`

约束：

- `summary_json` 不得包含 password、token、secret value、完整 prompt、未脱敏原文。

### 9.2 `query_logs`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 查询日志 ID |
| `enterprise_id` | `uuid` | 否 | FK `enterprises.id`, idx | 企业 ID |
| `request_id` | `text` | 否 | idx | 请求 ID |
| `trace_id` | `text` | 否 | idx | Trace ID |
| `user_id` | `uuid` | 否 | FK `users.id`, idx | 用户 ID |
| `kb_ids` | `uuid[]` | 否 | GIN | 请求知识库 |
| `query_hash` | `text` | 否 | idx | query hash |
| `status` | `text` | 否 | idx, CHECK `query_status` | success/failed/denied |
| `degraded` | `boolean` | 否 | idx | 是否降级 |
| `degrade_reason` | `text` | 是 | idx | 降级原因 |
| `config_version` | `integer` | 否 | idx | 配置版本 |
| `permission_version` | `integer` | 否 | idx | 权限版本 |
| `permission_filter_hash` | `text` | 否 | idx | 权限过滤 hash |
| `index_version_hash` | `text` | 是 | idx | active index 集合 hash |
| `model_route_hash` | `text` | 是 | idx | 模型路由 hash |
| `latency_ms` | `integer` | 否 | idx | 总耗时 |
| `candidate_count` | `integer` | 否 |  | 候选数 |
| `citation_count` | `integer` | 否 |  | 引用数 |
| `error_code` | `text` | 是 | idx | 错误码 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |

索引：

- `idx_query_logs_admin(enterprise_id, user_id, status, degraded, created_at desc)`
- `idx_query_logs_config_permission(enterprise_id, config_version, permission_version)`

### 9.3 `model_call_logs`

| 字段 | 类型 | Null | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | `uuid` | 否 | PK | 模型调用日志 ID |
| `enterprise_id` | `uuid` | 是 | FK `enterprises.id`, idx | 企业 ID |
| `request_id` | `text` | 是 | idx | 请求 ID |
| `trace_id` | `text` | 否 | idx | Trace ID |
| `config_version` | `integer` | 是 | idx | 调用使用的配置版本，setup 依赖测试阶段可为空 |
| `caller` | `text` | 否 | idx | query/import/worker 等 |
| `model_type` | `text` | 否 | idx | embedding/rerank/chat |
| `model_name` | `text` | 否 | idx | 模型名 |
| `model_version` | `text` | 是 | idx | 模型版本 |
| `model_route_hash` | `text` | 否 | idx | 路由 hash |
| `status` | `text` | 否 | idx, CHECK `model_call_status` | success/failed/degraded |
| `degraded` | `boolean` | 否 | idx | 是否降级 |
| `latency_ms` | `integer` | 否 | idx | 耗时 |
| `token_usage_json` | `jsonb` | 是 |  | token 用量 |
| `prompt_hash` | `text` | 是 | idx | prompt hash |
| `input_hash` | `text` | 是 | idx | 输入 hash |
| `output_hash` | `text` | 是 | idx | 输出 hash |
| `error_code` | `text` | 是 | idx | 错误码 |
| `created_at` | `timestamptz` | 否 | idx | 创建时间 |

约束：

- 不保存完整 prompt、完整 query 或文档原文。

## 10. 关键外键与循环依赖处理

首批 migration 需要注意以下依赖：

1. 先创建 `enterprises`、`users` 时，`users.created_by` 可以先不加 FK，或创建后再补 FK。
2. `documents.current_version_id` 引用 `document_versions.id`，而 `document_versions.document_id` 引用 `documents.id`。migration 中先创建 nullable 字段，再补 FK。
3. `documents.permission_snapshot_id` 和 `chunks.permission_snapshot_id` 引用 `permission_snapshots.id`，而 `permission_snapshots.resource_id` 是多态资源 ID，不做数据库 FK。
4. `chunk_index_refs.keyword_id` 引用 `keyword_index_entries.id`，而 `keyword_index_entries.chunk_id` 引用 `chunks.id`。可以先创建 `keyword_index_entries`，再创建或补 `chunk_index_refs.keyword_id` FK。
5. `setup_tokens.jwt_jti` 引用 `jwt_tokens.jti`，签发 setup JWT 时先写 `jwt_tokens`，再写 `setup_tokens`。

## 11. 查询可见性不变量

一个 chunk 可以进入查询上下文，必须同时满足：

```text
documents.enterprise_id = current_enterprise
AND documents.kb_id IN requested_kbs
AND documents.lifecycle_status = 'active'
AND documents.index_status = 'indexed'
AND chunks.status = 'active'
AND index_versions.status = 'active'
AND chunk_index_refs.visibility_state = 'active'
AND keyword_index_entries.visibility_state = 'active' -- 关键词召回时
AND access_blocks(active) NOT EXISTS for knowledge_base/document/chunk
AND (indexed_permission_version >= required_permission_version OR 回源确认通过)
AND (
  documents.visibility = 'enterprise'
  OR documents.owner_department_id IN current_user_department_ids
)
```

数据库需要支持该条件的组合索引，但最终是否放行仍由 Permission Service 和候选片段准入校验共同决定。

## 12. 唯一约束清单

| 约束 | 表 | 字段 |
| --- | --- | --- |
| `uq_setup_tokens_one_active` | `setup_tokens` | partial `status='active'` |
| `uq_config_versions_one_active` | `config_versions` | partial `status='active'` |
| `uq_system_configs_version_key` | `system_configs` | `config_version_id, key` |
| `uq_secrets_ref` | `secrets` | `secret_ref` |
| `uq_enterprises_code` | `enterprises` | `code` |
| `uq_users_enterprise_username` | `users` | `enterprise_id, lower(username)` |
| `uq_departments_enterprise_code` | `departments` | `enterprise_id, code` |
| `uq_departments_one_default` | `departments` | partial `is_default=true and status='active'` |
| `uq_user_dept_active` | `user_department_memberships` | partial active relation |
| `uq_roles_enterprise_code` | `roles` | `enterprise_id, code` |
| `uq_role_bindings_active_enterprise` | `role_bindings` | partial enterprise active binding |
| `uq_role_bindings_active_scoped` | `role_bindings` | partial scoped active binding |
| `uq_resource_policies_version` | `resource_policies` | `enterprise_id, resource_type, resource_id, version` |
| `uq_resource_policies_active` | `resource_policies` | partial active policy |
| `uq_folders_root_name` | `folders` | root folder name |
| `uq_folders_child_name` | `folders` | child folder sibling name |
| `uq_document_versions_no` | `document_versions` | `enterprise_id, document_id, version_no` |
| `uq_document_versions_active` | `document_versions` | partial active version |
| `uq_chunks_version_ordinal` | `chunks` | `enterprise_id, document_version_id, ordinal` |
| `uq_index_versions_active_doc` | `index_versions` | partial active index per document |
| `uq_import_jobs_idempotency` | `import_jobs` | partial expression idempotency key |

## 13. 查询索引清单

| 场景 | 推荐索引 |
| --- | --- |
| 用户登录 | `users(enterprise_id, lower(username))` |
| JWT 校验 | `jwt_tokens(jti)`、`jwt_tokens(status, expires_at)` |
| 当前用户部门 | `user_department_memberships(enterprise_id, user_id, status)` |
| 当前用户角色 | `role_bindings(enterprise_id, user_id, status)` |
| 权限过滤 | `documents(enterprise_id, visibility, owner_department_id, lifecycle_status, index_status)` |
| 知识库列表 | `knowledge_bases(enterprise_id, status, owner_department_id)` |
| 文档列表 | `documents(enterprise_id, kb_id, lifecycle_status, index_status, updated_at desc)` |
| chunk 回源 | `chunks(enterprise_id, document_id, document_version_id, status)` |
| active index | `index_versions(enterprise_id, document_id, status)` |
| 索引引用 | `chunk_index_refs(index_version_id, visibility_state, indexed_permission_version)` |
| 关键词召回 | `keyword_index_entries using gin(search_tsv)` |
| access block | `access_blocks(enterprise_id, resource_type, resource_id, status, expires_at)` |
| Worker 领取任务 | `import_jobs(status, next_retry_at, locked_until, created_at)` |
| 审计查询 | `audit_logs(enterprise_id, event_name, result, risk_level, created_at desc)`、`audit_logs(enterprise_id, config_version, permission_version, created_at desc)` |
| 查询日志 | `query_logs(enterprise_id, user_id, status, degraded, created_at desc)` |
| 模型调用日志 | `model_call_logs(enterprise_id, config_version, model_type, status, created_at desc)` |
| 缓存过期 | `query_cache_entries(expires_at)` |

## 14. 首批 Alembic migration 草案

建议拆分为以下 migration，避免一个文件过大且便于回滚定位：

### 14.1 `0001_extensions_and_base_enums`

- 启用必要扩展：`pgcrypto`、`btree_gin`。
- 如果使用 DB 生成 UUID，可启用 `uuid-ossp`；P0 推荐应用生成 UUIDv7。
- 创建 CHECK 约束辅助函数或直接在表定义中写 CHECK。

### 14.2 `0002_setup_config_auth_org`

创建：

- `system_state`
- `config_versions`
- `system_configs`
- `secrets`
- `enterprises`
- `users`
- `user_credentials`
- `jwt_tokens`
- `setup_tokens`
- `departments`
- `user_department_memberships`

初始化数据：

- 默认 `system_state.initialized=false`
- 默认 schema migration version

### 14.3 `0003_roles_permissions`

创建：

- `roles`
- `role_bindings`
- `resource_policies`
- `permission_snapshots`

初始化数据：

- P0 内置角色定义。
- 默认 employee/system_admin 等 scopes。

### 14.4 `0004_knowledge_document_index`

创建：

- `knowledge_bases`
- `folders`
- `documents`
- `document_versions`
- `chunks`
- `index_versions`
- `keyword_index_entries`
- `chunk_index_refs`
- `access_blocks`

注意：

- `documents.current_version_id` 和 `documents.permission_snapshot_id` 可在表创建后补 FK。
- active index 和 active document 相关 partial unique index 在表创建后补。

### 14.5 `0005_jobs_audit_cache`

创建：

- `import_jobs`
- `audit_logs`
- `query_logs`
- `model_call_logs`
- `query_cache_entries`

### 14.6 `0006_indexes_and_constraints`

- 补充所有 partial unique indexes。
- 补充 GIN indexes。
- 补充查询链路组合索引。
- 补充软删除、active 状态查询索引。

## 15. 软删除与阻断策略

- 用户、部门、知识库、文件夹、文档都使用软删除。
- 文档、chunk、知识库删除必须先写 `access_blocks(status='active')`。
- `documents.lifecycle_status='deleted'` 和 `chunks.status='deleted'` 是事实状态。
- `chunk_index_refs.visibility_state='blocked'` 是索引可见性阻断状态。
- 物理删除 Qdrant point、关键词索引和对象存储对象是异步清理，不是安全边界。

删除文档事务最小步骤：

```text
1. INSERT access_blocks(resource_type='document', reason='deleted', status='active')
2. UPDATE documents SET lifecycle_status='deleted', index_status='blocked', deleted_at=now()
3. UPDATE chunks SET status='deleted', deleted_at=now()
4. UPDATE chunk_index_refs SET visibility_state='blocked'
5. INSERT import_jobs(job_type='index_delete', status='queued')
6. INSERT audit_logs(event_name='document.deleted', ...)
```

## 16. P0 实现检查清单

- [x] 所有租户业务表都有 `enterprise_id`。
- [x] 所有 global 表都明确 scope 和访问边界。
- [x] 所有表都有主键。
- [x] 所有高频读取路径都有组合索引。
- [x] 所有 active 唯一语义使用 partial unique index。
- [x] 所有状态字段有 CHECK 约束。
- [x] 所有软删除表有 `deleted_at` 或等价状态。
- [x] 文档、chunk、索引、权限快照之间可以对账。
- [x] draft index、deleted document、blocked resource 不能被查询命中。
- [x] Secret value 不进入 `system_configs`、`audit_logs`、`query_logs`、`model_call_logs`。
