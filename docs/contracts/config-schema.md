# 初始化配置与 active_config v1 Schema

## 1. 文档目标

本文定义 Little Bear RAG 后端 P0 阶段的初始化配置和 `active_config v1` 契约，作为 `setup-config-validations`、`setup-initialization`、Config Service、ServiceBootstrap、OpenAPI、数据库 Schema 和本地开发环境的共同输入。

机器可校验 JSON Schema 已落地到 `docs/contracts/config.schema.json`。本文负责说明字段语义、校验意图和运行约束；实现中的 schema 校验应以 `docs/contracts/config.schema.json` 为准。

P0 目标：

- 系统启动配置只包含数据库连接和进程参数。
- 初始化接口一次性提交首个可运行配置。
- `active_config v1` 足以驱动 ServiceBootstrap 初始化 Redis、Secret Store、对象存储、向量库、关键词检索、外部模型服务、审计和限流。
- 本地开发和自动化测试使用外部 embedding、rerank、LLM 服务，不再内置模型模拟服务。
- Secret value 不进入 active config、API 响应、普通日志或审计摘要。

P0 不实现：

- 完整配置审批。
- 通用配置回滚平台。
- 复杂配置 diff 工作流。
- 多模型供应商生产级动态路由。
- 真实大模型高可用调度。

## 2. 顶层结构

初始化请求由两部分组成：

```json
{
  "setup": {
    "admin": {},
    "organization": {},
    "roles": {},
    "model_provider_secrets": {}
  },
  "config": {}
}
```

- `setup`：初始化实体数据，写入用户、组织、角色和角色绑定等业务表，不写入 active config。
- `setup.model_provider_secrets`：仅初始化写入时允许携带的模型访问密钥明文，后端接收后立即加密写入 Secret Store，并从请求中剥离，不进入 active config、普通日志或审计摘要。
- `config`：初始化运行配置，写入 `system_configs` 和 `config_versions`，发布为 `active_config v1`。

## 3. setup Schema

### 3.1 setup.admin

```json
{
  "username": "admin",
  "display_name": "System Admin",
  "initial_password": "ChangeMe_123456",
  "email": "admin@example.com",
  "phone": null
}
```

字段规则：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `username` | string | 是 | 3 到 64 字符，企业内唯一 |
| `display_name` | string | 是 | 1 到 128 字符 |
| `initial_password` | string | 是 | 必须满足 `auth` 密码策略，只允许初始化请求携带，不写入日志或审计摘要 |
| `email` | string/null | 否 | 如提供必须是 email 格式 |
| `phone` | string/null | 否 | P0 只保存，不做短信验证 |

### 3.2 setup.organization

```json
{
  "enterprise": {
    "name": "Default Enterprise",
    "code": "default"
  },
  "departments": [
    {
      "name": "Default Department",
      "code": "default",
      "is_default": true
    }
  ]
}
```

字段规则：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `enterprise.name` | string | 是 | 1 到 128 字符 |
| `enterprise.code` | string | 是 | 1 到 64 字符，初始化企业内唯一 |
| `departments` | array | 是 | 至少 1 个部门 |
| `departments[].name` | string | 是 | 1 到 128 字符 |
| `departments[].code` | string | 是 | 1 到 64 字符，企业内唯一 |
| `departments[].is_default` | boolean | 是 | 必须且只能有一个默认部门 |

P0 部门不建模上下级递归，不包含 `parent_id`、`path` 或 closure table。

### 3.3 setup.roles

```json
{
  "builtin_roles": [
    "system_admin",
    "security_admin",
    "audit_admin",
    "department_admin",
    "knowledge_base_admin",
    "employee"
  ],
  "admin_role": "system_admin",
  "default_user_role": "employee"
}
```

字段规则：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `builtin_roles` | string[] | 是 | 必须包含 P0 内置角色全集 |
| `admin_role` | string | 是 | P0 固定为 `system_admin` |
| `default_user_role` | string | 是 | P0 固定为 `employee` |

### 3.4 setup.model_provider_secrets

```json
{
  "embedding_auth_token": null,
  "rerank_auth_token": null,
  "llm_auth_token": null
}
```

字段规则：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `embedding_auth_token` | string/null | 否 | 外部 embedding provider 需要鉴权时填写明文 token；仅用于初始化请求 |
| `rerank_auth_token` | string/null | 否 | 外部 rerank provider 需要鉴权时填写明文 token；仅用于初始化请求 |
| `llm_auth_token` | string/null | 否 | 外部 LLM provider 需要鉴权时填写明文 token；仅用于初始化请求 |

后端处理规则：

- 若字段有值，后端必须在初始化事务内加密写入 PostgreSQL `secrets` 表。
- 默认写入 ref 分别为 `secret://rag/model/embedding-api-key`、`secret://rag/model/rerank-api-key`、`secret://rag/model/llm-api-key`。
- 写入完成后，后端自动把 `config.model_gateway.providers.<name>.auth_token_ref` 改写为对应 ref。
- 明文 token 不得写入 active config、接口响应、普通日志、审计摘要或页面回显。

## 4. active_config v1 Schema

`active_config v1` 是运行配置 bundle。P0 使用单个 global bundle 作为最小实现，后续可以由 Config Service 拆分为多条 `system_configs` 记录。

```json
{
  "schema_version": 1,
  "config_version": 1,
  "scope": {
    "type": "global",
    "id": "global"
  },
  "secret_provider": {},
  "redis": {},
  "storage": {},
  "vector_store": {},
  "keyword_search": {},
  "model_gateway": {},
  "model": {},
  "llm": {},
  "auth": {},
  "retrieval": {},
  "chunk": {},
  "import": {},
  "permission": {},
  "security": {},
  "cache": {},
  "rate_limit": {},
  "timeout": {},
  "degrade": {},
  "audit": {},
  "observability": {}
}
```

顶层必填字段：

| 字段 | 类型 | 必填 | 规则 |
| --- | --- | --- | --- |
| `schema_version` | integer | 是 | P0 固定为 `1` |
| `config_version` | integer | 是 | 运行配置版本；首次初始化发布为 `1`，后续发布必须与数据库 `config_versions.version` 一致 |
| `scope.type` | string | 是 | P0 固定为 `global` |
| `scope.id` | string | 是 | P0 固定为 `global` |

## 5. Secret 引用规则

Secret value 不得出现在 `active_config v1`。

Secret 引用格式：

```text
secret://<namespace>/<path>
```

P0 默认命名空间：

```text
secret://rag/<service>/<name>
```

示例：

```json
{
  "storage": {
    "access_key_ref": "secret://rag/minio/access-key",
    "secret_key_ref": "secret://rag/minio/secret-key"
  },
  "auth": {
    "jwt_signing_key_ref": "secret://rag/auth/jwt-signing-key"
  }
}
```

校验规则：

- 必须以 `secret://` 开头。
- namespace 只能包含小写字母、数字、`-` 和 `_`。
- path 至少包含两级，例如 `minio/access-key`。
- `setup-config-validations` 必须确认引用存在且当前 Secret Provider 可读取。
- API 响应和审计摘要只返回 Secret ref，不返回 Secret value。

## 6. 配置分组

### 6.1 secret_provider

```json
{
  "type": "postgres_encrypted",
  "endpoint": "postgres://local-secrets",
  "auth_method": "database",
  "secret_ref_policy": {
    "allowed_namespaces": ["rag"],
    "required_prefix": "secret://rag/"
  }
}
```

约束：

- P0 推荐 `postgres_encrypted`。
- 可以保留 `vault`、`kms` 等枚举扩展，但不得作为 P0 必需依赖。

### 6.2 redis

```json
{
  "url": "redis://redis:6379/0",
  "pool": {
    "max_connections": 32,
    "connect_timeout_ms": 500,
    "socket_timeout_ms": 1000,
    "retry_on_timeout": true
  },
  "cache_strategy": {
    "permission_context_enabled": true,
    "query_cache_enabled": true,
    "rate_limit_enabled": true,
    "lock_enabled": true,
    "config_notify_enabled": true
  }
}
```

### 6.3 storage

```json
{
  "provider": "minio",
  "minio_endpoint": "http://minio:9000",
  "bucket": "little-bear-rag",
  "region": "local",
  "tls_enabled": false,
  "access_key_ref": "secret://rag/minio/access-key",
  "secret_key_ref": "secret://rag/minio/secret-key",
  "object_key_prefix": "p0/"
}
```

### 6.4 vector_store

```json
{
  "provider": "qdrant",
  "qdrant_base_url": "http://qdrant:6333",
  "api_key_ref": null,
  "collection_prefix": "little_bear_p0",
  "distance": "cosine",
  "write_check_enabled": true,
  "delete_check_enabled": true
}
```

约束：

- `distance` 可选值：`cosine`、`dot`、`euclidean`。
- `api_key_ref` 可为空，但必须显式声明为 `null`。
- 如果 Qdrant 开启了 API Key 鉴权，必须填写可读的 Secret ref，例如 `secret://rag/qdrant/api-key`。

### 6.5 keyword_search

```json
{
  "provider": "postgres_full_text",
  "language": "zh",
  "keyword_analyzer": "zhparser",
  "dictionary_version": "dict-p0-v1",
  "synonym_version": "syn-p0-v1",
  "stopwords_version": "stop-p0-v1",
  "boosts": {
    "title": 2.0,
    "heading_path": 1.5,
    "body": 1.0,
    "tags": 1.2
  }
}
```

P0 默认使用 PostgreSQL Full Text + `zhparser` 作为中文分词方案。企业词库、同义词、停用词和更细粒度的中文分词治理进入后续阶段；如果运行环境不提供 `zhparser`，则必须退回预分词字段方案，不能直接宣称中文关键词召回可用于生产。

### 6.6 model_gateway

P0 直接配置外部 embedding、rerank 和 LLM 服务。下面的 `tei-embedding` 和 `tei-rerank` 是 `docker-compose.yml` 提供的本地演示 provider，不是强制部署项；实际使用可以删除对应 compose service，并替换为企业模型代理、远程 TEI 或云厂商 provider URL。当前 compose 不创建 LLM 容器，`providers.llm.base_url` 必须替换为真实 OpenAI-compatible 服务地址。默认配置：

```json
{
  "mode": "external",
  "auth_token_ref": null,
  "providers": {
    "embedding": {
      "type": "tei",
      "base_url": "http://tei-embedding:80",
      "auth_token_ref": null,
      "healthcheck_path": "/health",
      "embeddings_path": "/v1/embeddings"
    },
    "rerank": {
      "type": "tei",
      "base_url": "http://tei-rerank:80",
      "auth_token_ref": null,
      "healthcheck_path": "/health",
      "rerank_path": "/rerank"
    },
    "llm": {
      "type": "openai_compatible",
      "base_url": "http://llm-provider:8000",
      "auth_token_ref": null,
      "healthcheck_path": "/health",
      "chat_completions_path": "/v1/chat/completions"
    }
  },
  "routes": {
    "embedding": {
      "online_default": "jina‑embeddings‑v2‑base‑zh",
      "batch_default": "jina‑embeddings‑v2‑base‑zh"
    },
    "rerank": {
      "default": "bge-reranker-base"
    },
    "llm": {
      "default": "qwen3-4b",
      "fallback": "qwen3-4b"
    }
  },
  "healthcheck": {
    "path": "/health",
    "timeout_ms": 2000,
    "failure_threshold": 3
  }
}
```

约束：

- `mode` 固定为 `external`。
- `providers.embedding` 和 `providers.rerank` 默认使用 TEI HTTP 服务。
- `providers.llm` 使用 OpenAI-compatible Chat Completions 接口，可以指向 vLLM、商业模型代理或企业内模型服务。
- `auth_token_ref` 支持两层配置：`model_gateway.auth_token_ref` 是三个 provider 共用的兜底 token；`providers.<name>.auth_token_ref` 是 provider 级 token，优先级更高。
- 初始化页面允许通过 `setup.model_provider_secrets` 直接输入模型访问密钥明文；后端会加密写入 Secret Store，并在 active config 中只保存 `secret://rag/...` 引用。
- active config 中不得保存明文 API Key。
- 每次模型调用必须生成 `model_route_hash`。
- 普通日志不得记录完整 prompt。

### 6.7 model

```json
{
  "embedding_model": "jina‑embeddings‑v2‑base‑zh",
  "embedding_version": "2026-04-30",
  "embedding_dimension": 768,
  "embedding_normalize": true,
  "embedding_tokenizer_version": "jina‑embeddings‑v2‑base‑zh-tokenizer",
  "rerank_model": "bge-reranker-base",
  "llm_model": "qwen3-4b",
  "llm_fallback_model": "qwen3-4b"
}
```

约束：

- `embedding_dimension` 必须与向量索引 collection 维度一致。
- 查询 embedding 和导入 embedding 必须使用兼容模型版本。

### 6.8 llm

```json
{
  "temperature": 0.1,
  "max_tokens": 800,
  "first_token_timeout_ms": 3000,
  "total_timeout_ms": 20000,
  "retry_policy": {
    "max_retries": 0,
    "backoff_ms": 0
  }
}
```

### 6.9 auth

```json
{
  "password_min_length": 12,
  "password_require_uppercase": true,
  "password_require_lowercase": true,
  "password_require_digit": true,
  "password_require_symbol": false,
  "login_failure_limit": 5,
  "lock_minutes": 15,
  "access_token_ttl_minutes": 30,
  "refresh_token_ttl_minutes": 10080,
  "jwt_issuer": "little-bear-rag",
  "jwt_audience": "little-bear-internal",
  "jwt_signing_key_ref": "secret://rag/auth/jwt-signing-key"
}
```

### 6.10 retrieval

```json
{
  "vector_top_k": 20,
  "keyword_top_k": 20,
  "fusion_method": "rrf",
  "fusion_params": {
    "rrf_k": 60,
    "title_boost": 1.2,
    "freshness_boost": 1.0,
    "low_ocr_penalty": 0.8
  },
  "rerank_input_top_k": 20,
  "final_context_top_k": 8,
  "max_context_tokens": 6000,
  "rewrite_enabled": false,
  "expansion_enabled": false
}
```

P0 rewrite 和 expansion 默认关闭；可以由规则或外部 LLM provider 开启。

### 6.11 chunk

```json
{
  "default_size_tokens": 800,
  "overlap_tokens": 120,
  "strategy": {
    "mode": "heading_paragraph",
    "preserve_tables": true,
    "preserve_code_blocks": true,
    "preserve_contract_clauses": true
  }
}
```

### 6.12 import

```json
{
  "max_file_mb": 50,
  "allowed_file_types": ["pdf", "docx", "txt", "md"],
  "max_concurrent_jobs": 4,
  "department_concurrent_jobs": 2,
  "user_concurrent_jobs": 1,
  "file_concurrency_per_job": 2,
  "embedding_batch_size": 32,
  "index_batch_size": 128,
  "retry_policy": {
    "max_retries": 3,
    "initial_delay_seconds": 30,
    "max_delay_seconds": 600,
    "dead_letter_enabled": true
  }
}
```

### 6.13 permission

```json
{
  "default_user_role": "employee",
  "default_visibility": "department",
  "cache_ttl_seconds": 300,
  "tightening_block_policy": {
    "write_access_block_first": true,
    "block_old_index_refs": true,
    "fail_closed": true
  }
}
```

约束：

- P0 文档可见性只支持 `department` 和 `enterprise`。
- 权限判断不依赖 LLM。

### 6.14 security

```json
{
  "require_citation": true,
  "prompt_leakage_policy": {
    "block_internal_prompt_leakage": true,
    "block_secret_ref_leakage": true
  },
  "pii_redaction_policy": {
    "enabled": true,
    "redact_logs": true,
    "redact_audit_summary": true
  }
}
```

### 6.15 cache

```json
{
  "permission_context_ttl_seconds": 300,
  "query_embedding_enabled": true,
  "query_embedding_ttl_seconds": 3600,
  "retrieval_result_enabled": true,
  "retrieval_result_ttl_seconds": 300,
  "final_answer_enabled": false,
  "final_answer_ttl_seconds": 0,
  "cross_user_final_answer_allowed": false
}
```

P0 默认关闭最终答案缓存，降低串权风险。

### 6.16 rate_limit

```json
{
  "query_qps_per_user": 2,
  "ip": {
    "qps": 20,
    "burst": 40
  },
  "department": {
    "query_qps": 20,
    "import_concurrency": 2
  },
  "kb": {
    "query_qps": 50
  },
  "api_key": {
    "qps": 10
  },
  "model_pool": {
    "qps": 10
  }
}
```

### 6.17 timeout

```json
{
  "query_total_ms": 8000,
  "auth_permission_ms": 100,
  "rewrite_ms": 300,
  "embedding_ms": 500,
  "vector_search_ms": 500,
  "keyword_search_ms": 500,
  "rerank_ms": 800,
  "context_ms": 200,
  "postprocess_ms": 300
}
```

### 6.18 degrade

```json
{
  "rewrite_timeout": "use_original_query",
  "embedding_timeout": "keyword_only",
  "vector_unavailable": "keyword_and_metadata",
  "keyword_unavailable": "vector_and_metadata",
  "rerank_timeout": "fusion_score",
  "llm_timeout": "return_retrieval_with_citations",
  "model_pool_overloaded": "return_retryable_degraded_response",
  "import_backlog": "slow_down_import"
}
```

### 6.19 audit

```json
{
  "sink": "postgres",
  "retention_days": 180,
  "query_text_mode": "hash",
  "record_full_prompt": false,
  "snippet_max_chars": 300,
  "pii_redaction_enabled": true
}
```

约束：

- `record_full_prompt` P0 必须为 `false`。
- `query_text_mode` 可选值：`none`、`hash`、`plain`；P0 推荐 `hash`。

### 6.20 observability

```json
{
  "metrics_enabled": true,
  "trace_enabled": true,
  "alert_thresholds": {
    "active_config_load_failed": 1,
    "permission_violation_rate": 0,
    "draft_index_exposure_count": 0,
    "import_failure_rate": 0.1,
    "worker_queue_backlog": 100,
    "llm_timeout_rate": 0.2
  }
}
```

## 7. ServiceBootstrap ready 规则

ServiceBootstrap 输入只能是数据库中的 `active_config v1`。

启动顺序：

1. 读取 `active_config v1`。
2. 初始化 Secret Provider。
3. 解析 Secret refs，但不把 Secret value 写入日志。
4. 初始化 Redis。
5. 初始化 ObjectStorage。
6. 初始化 VectorStore。
7. 初始化 KeywordSearch。
8. 初始化外部 embedding、rerank 和 LLM 服务 adapter。
9. 初始化 Audit Sink。
10. 初始化 Rate Limiter。
11. 标记 service ready。

Ready 判定：

| 模块 | P0 ready 条件 |
| --- | --- |
| Secret Provider | 可读取所有必需 Secret ref |
| Redis | ping 成功，锁和计数器基础命令可用 |
| ObjectStorage | bucket 存在或可创建，测试对象可写入和删除 |
| VectorStore | Qdrant 可连接，collection 维度与 `model.embedding_dimension` 一致 |
| KeywordSearch | PostgreSQL Full Text 最小查询可执行 |
| Model Provider Adapter | 外部 embedding、rerank 和 LLM provider health 成功 |
| Audit Sink | `audit_logs` 可写入 |
| Rate Limiter | Redis 或降级计数器可用 |

任一关键模块未 ready 时：

- `/health/live` 可以返回 live。
- `/health/ready` 必须返回 not ready。
- 普通业务 API 必须拒绝服务。
- 不得回退到环境变量业务配置。

## 8. setup-config-validations 校验规则

校验分层：

1. setup JWT 校验。
2. 初始化状态校验。
3. JSON schema 校验。
4. Secret ref 格式和可读性校验。
5. 管理员密码策略校验。
6. 依赖连通性校验。
7. 权限和缓存安全策略校验。
8. 外部模型 provider 健康校验。
9. 返回结构化校验结果。

校验响应建议：

```json
{
  "valid": false,
  "errors": [
    {
      "error_code": "CONFIG_SCHEMA_INVALID",
      "path": "config.storage.bucket",
      "message": "bucket is required",
      "retryable": false
    }
  ],
  "warnings": []
}
```

## 9. 错误码

| 错误码 | 场景 | retryable |
| --- | --- | --- |
| `CONFIG_SCHEMA_INVALID` | JSON schema 校验失败 | false |
| `CONFIG_SECRET_REF_INVALID` | Secret ref 格式非法 | false |
| `CONFIG_SECRET_UNREADABLE` | Secret Provider 无法读取 Secret | true |
| `CONFIG_DEPENDENCY_FAILED` | Redis、MinIO、Qdrant、KeywordSearch 或外部模型 provider 校验失败 | true |
| `CONFIG_MODEL_PROVIDER_INVALID` | 外部模型 provider 配置缺失或不兼容 | false |
| `CONFIG_EMBEDDING_DIMENSION_INVALID` | embedding 维度与向量库配置不一致 | false |
| `CONFIG_CACHE_UNSAFE` | 缓存策略可能跨用户或跨权限复用最终答案 | false |
| `CONFIG_PROMPT_LOGGING_UNSAFE` | P0 尝试记录完整 prompt | false |
| `CONFIG_PERMISSION_UNSAFE` | 权限收紧策略不是 fail closed | false |
| `CONFIG_BOOTSTRAP_NOT_READY` | ServiceBootstrap 未 ready | true |

## 10. OpenAPI 对接要求

OpenAPI 必须为以下接口引用本文 schema：

- `POST /internal/v1/setup-config-validations`
- `PUT /internal/v1/setup-initialization`
- `GET /internal/v1/admin/configs`
- `GET /internal/v1/admin/configs/{key}`
- `PUT /internal/v1/admin/configs/{key}`
- `POST /internal/v1/admin/config-validations`

P0 管理后台配置 API 只要求：

- 读取配置。
- 保存或替换配置草稿。
- 校验配置。
- 发布 active config。

P0 不要求：

- 完整审批。
- 通用配置回滚。
- 复杂 diff 工作流。

## 11. 测试要求

P0 必测：

- 缺少任一顶层必填配置时校验失败。
- Secret value 出现在 active config 时校验失败。
- Secret ref 不可读时校验失败。
- `record_full_prompt=true` 时校验失败。
- `cache.cross_user_final_answer_allowed=true` 时校验失败。
- `permission.tightening_block_policy.fail_closed=false` 时校验失败。
- embedding 维度和 VectorStore collection 不一致时校验失败。
- 外部模型 provider 不可用时 ServiceBootstrap not ready。
- 使用外部模型配置可以完成初始化、导入、索引、查询和降级测试。
