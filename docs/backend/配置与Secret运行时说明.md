# 配置与 Secret 运行时说明

更新时间：2026-06-03

本文说明 Little Bear 交付版后端如何加载配置、保存密钥、校验运行依赖，以及配置变更如何影响 API 和 Worker。本文只描述交付版已经实现的逻辑。

## 1. 设计目标

配置体系的目标不是让 `.env` 承载所有参数，而是把业务运行配置收敛到数据库中的 active config，并通过 Secret Store 保存敏感值。

这样做的直接结果是：

- `.env` 只负责进程启动所需的最小参数。
- 业务模块不直接读取模型、MinIO、Qdrant、Redis、检索策略、权限策略等业务配置。
- API 和 Worker 通过 `ConfigService` 读取当前 active config。
- 配置发布前必须经过 schema 校验和依赖探测。
- 密钥以 `secret://...` 引用进入配置，真实 secret value 不进入配置 JSON。

## 2. `.env` 与 active config 的边界

### 2.1 `.env` 负责进程启动边界

当前 `apps/api/app/shared/settings.py` 只从环境变量读取启动层参数，主要包括：

- 数据库连接：`DATABASE_URL`、连接超时、连接池和 SSL mode。
- 进程信息：`APP_ENV`、`SERVICE_NAME`、`API_HOST`、`API_PORT`、`LOG_LEVEL`。
- 初始化辅助：`ADMIN_SETUP_URL`、`SETUP_TOKEN_LOG_ENABLED`、`SETUP_TOKEN_SIGNING_SECRET`。
- Secret Store 主密钥：`SECRET_STORE_MASTER_KEY`。

这些值用于让进程能启动、连接 PostgreSQL、执行迁移和进入初始化流程。它们不是业务决策配置。

### 2.2 active config 负责业务运行边界

业务配置存储在数据库配置版本中，由 `ConfigService` 加载 active config。当前 active config 覆盖的运行域包括：

- Redis 连接与基础依赖探测。
- MinIO 对象存储连接与访问密钥引用。
- Qdrant 向量库连接、collection 和 API key 引用。
- 关键词检索能力。
- embedding、rerank、LLM provider 路由、healthcheck 和认证 token 引用。
- JWT 签名密钥引用。
- 检索、重排、质量 gate、上下文、LLM、超时、降级、审计等策略。

业务模块必须通过 `ConfigService`、运行时 factory 或领域 service 获取这些配置。不能为了方便绕过 active config 直接读取 `.env`。

## 3. 为什么业务配置不直接从 `.env` 读取

当前系统的配置发布、依赖校验和审计都依赖数据库 active config。如果业务模块直接读取 `.env`，会带来几个明确问题：

- 配置管理页面无法真实控制运行配置。
- 配置发布前无法探测 MinIO、Qdrant、Redis、模型 provider 是否可用。
- API 与 Worker 可能在不同机器上读取到不同配置。
- Secret value 容易散落到环境变量、日志或前端展示。
- ServiceBootstrap 无法判断系统是否具备服务业务请求的条件。

因此当前设计采用“`.env` 启动进程，active config 决定业务运行”的边界。

## 4. Secret Store

Secret Store 由 `apps/api/app/modules/secrets/service.py` 实现，使用 PostgreSQL 存储加密密文。

### 4.1 secret_ref 规则

当前 secret 引用必须满足：

```text
secret://<namespace>/<service>/<name>
```

交付版约束要求 secret_ref 使用 `secret://rag/` 前缀。配置中只保存 secret_ref，不保存真实密钥。

### 4.2 加密与完整性

Secret Store 实现要点：

- 使用 `SECRET_STORE_MASTER_KEY` 派生 AES-256-GCM 加密密钥。
- 派生过程使用 HKDF-SHA256。
- AES-GCM 的 associated data 绑定 `secret_ref`，防止密文被复制到另一个 ref 后仍可解密。
- 存储 HMAC-SHA256 value hash，用于不暴露明文的校验和审计。
- secret 列表接口不返回明文。

`SECRET_STORE_MASTER_KEY` 是启动层必须配置的关键密钥。它不是业务配置，不能放入 active config。

### 4.3 当前依赖的 secret 类型

ServiceBootstrap 当前会检查以下 secret 引用：

- MinIO access key。
- MinIO secret key。
- JWT signing key。
- Qdrant API key。
- model gateway auth token。
- embedding / rerank / LLM provider auth token。

其中 MinIO 和 JWT 是必需依赖；Qdrant 和模型 provider 的认证 token 是否必需，取决于 active config 是否配置了对应 auth ref。

## 5. 配置版本生命周期

配置版本由配置管理能力创建、编辑、发布、归档。当前发布链路由 `ConfigPublisher` 执行。

发布过程如下：

1. 加载目标配置版本并加锁。
2. 校验版本状态是否允许发布。
3. 将版本标记为 `validating`。
4. 执行配置 schema 校验。
5. 执行 ServiceBootstrap 依赖探测。
6. 校验失败时将版本标记为 `failed`，记录审计，保留原 active config。
7. 校验成功时停用旧 active config，激活新版本。
8. 更新系统 active config version。
9. 持久化 bootstrap 状态。
10. 失效进程内配置缓存。
11. 记录配置发布审计。

配置发布失败不会自动覆盖当前正在使用的 active config。

## 6. ServiceBootstrap 校验内容

ServiceBootstrap 是系统是否可以开放普通业务 API 的门禁。当前校验内容包括：

- 数据库 migration revision 是否达到当前期望版本。
- active config 是否存在。
- active config schema 是否有效。
- secret_ref 是否能在 Secret Store 中找到并解密。
- Redis 是否可连接。
- MinIO 健康检查是否通过。
- Qdrant 健康检查是否通过。
- 关键词检索能力是否可用。
- embedding、rerank、LLM provider healthcheck 是否通过。

系统初始化完成但 active config 缺失或 bootstrap 不通过时，业务 API 会被 setup guard 拒绝，返回 `SERVICE_BOOTSTRAP_UNAVAILABLE`。

## 7. 运行时读取方式

### 7.1 API

API route 不直接构造 MinIO、Qdrant 或模型 provider。route 只负责 HTTP 入参、认证依赖和调用 service。领域 service 或 runtime factory 通过 active config 组装外部依赖。

查询、导入、索引、配置、审计等模块均应遵守这个边界。

### 7.2 Worker

Worker 负责导入、解析、切块、embedding 和索引发布。Worker 的业务依赖也来自 active config，而不是 `.env`。

Worker 自身的进程参数可以由启动参数或环境变量控制，例如 worker id、轮询间隔、锁超时等。这些参数只影响 Worker 进程行为，不决定业务 provider、对象存储、向量库或检索策略。

## 8. 配置缓存

当前 `ConfigCache` 是每个 API / Worker 进程内的轻量缓存，默认 TTL 为 5 秒。发布配置后会显式 invalidate 当前进程缓存。

需要注意：

- 缓存的是 active config 快照，不缓存 secret 明文。
- 多进程之间当前依赖 TTL 和下一次读取刷新。
- 当前 Redis 还没有承担配置变更通知通道。

## 9. 配置变更对 API 和 Worker 的影响

配置发布成功后：

- 新的业务请求会在缓存失效后读取新的 active config。
- 查询链路会使用新的模型 provider、检索策略、超时和降级策略。
- 导入和索引链路会使用新的对象存储、embedding、Qdrant 和关键词检索配置。
- Worker 领取或推进任务时会使用新的运行时配置。
- 如果新配置无法通过依赖探测，则不会成为 active config。

配置变更不会回滚已经完成的导入结果或已经写入的日志。涉及索引维度、collection、embedding 模型等关键变更时，应结合重建索引能力处理已有文档。

## 10. 排障入口

常见问题排查路径：

- 登录或业务接口返回 `SERVICE_BOOTSTRAP_UNAVAILABLE`：检查 active config 是否存在、配置发布是否失败、ServiceBootstrap 检查结果。
- 模型 provider 返回 401：检查 active config 中 provider auth token ref 是否配置，Secret Store 是否存在对应 secret，模型调用日志是否记录 HTTP 错误。
- MinIO / Qdrant 不可用：检查配置管理中的连接参数、Secret Store、ServiceBootstrap 状态和对应外部服务健康状态。
- Worker 导入失败：检查 import job 阶段、对象存储配置、embedding provider、Qdrant collection 和索引版本状态。

## 11. 交付边界

- Redis 已作为基础设施依赖接入 ServiceBootstrap，业务缓存和配置通知不属于交付版运行闭环。
- active config 缓存是进程内 TTL 缓存，不是跨进程强一致配置广播。
- Secret Store 依赖 `SECRET_STORE_MASTER_KEY`，该主密钥丢失或更换会导致既有 secret 无法解密。
