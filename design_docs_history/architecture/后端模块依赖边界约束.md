# 后端模块依赖边界约束

更新时间：2026-05-30

## 目标

本文档定义后端模块之间的依赖方向、职责边界和禁止事项，用于约束后续重构。

核心目标：

- 避免 route 层、service 层、runtime 层职责混杂。
- 避免 public/admin DTO 互相复用导致字段暴露边界失控。
- 避免非 admin 模块依赖 `AdminService` 内部能力。
- 避免业务代码直接读取 secret、直接构造外部 adapter。
- 让后续拆分 `admin`、`query`、`setup`、`config`、`import_pipeline`、`indexing` 时有稳定边界。

## 分层职责

### `api/routes`

职责：

- 处理 HTTP 入参、认证依赖、分页参数、响应状态码。
- 调用 module service 或 facade。
- 调用 presenter 将 service 返回值转换为 API schema。

允许依赖：

- `api/schemas/*`
- `api/dependencies/*`
- `api/presenters/*`
- `modules/<domain>/*` 的公开 service/facade/error
- `db/session.py` 之类的数据库 session 依赖

禁止依赖：

- 禁止直接读取 secret。
- 禁止直接构造外部 adapter，例如 MinIO、Qdrant、HTTP 模型 provider。
- 禁止直接写复杂 SQL。
- 禁止直接实现业务权限判断。
- 禁止跨模块依赖内部管理 service，例如 `permissions` route 依赖 `AdminService`。

### `api/dependencies`

职责：

- 封装 FastAPI dependency。
- 统一认证、request_id、分页参数、公共 header 解析。

允许依赖：

- `modules/auth`
- `shared`
- `db/session.py`

禁止依赖：

- 禁止调用 admin、knowledge、query 等业务管理 service。
- 禁止写业务数据。

### `api/schemas`

职责：

- 定义 API 请求和响应 DTO。
- 按暴露边界区分 public/admin/config/audit/query 等 schema。

允许依赖：

- `api/schemas/common.py`
- Pydantic、标准库类型

禁止依赖：

- 禁止依赖 `modules/*`。
- 禁止 admin schema 复用 public response DTO。
- 禁止 public schema 复用 admin response DTO。
- 禁止把内部 hash、trace、完整配置、全文 chunk 放进列表 DTO。

### `api/presenters`

职责：

- 将 service 返回的内部对象转换为 API schema。
- 执行展示字段裁剪、ID 到可读名称的展示映射。

允许依赖：

- `api/schemas/*`
- service 返回的数据结构

禁止依赖：

- 禁止访问数据库。
- 禁止执行权限判断。
- 禁止调用外部 provider。

### `modules/<domain>`

职责：

- 承担业务规则、事务编排、权限校验调用、领域状态变更。
- 每个模块只暴露清晰 service/facade，不暴露内部 repository/helper 给 route 直接调用。

允许依赖：

- 本模块内部文件。
- `shared`
- `db`
- 明确的下游 module service。
- adapter protocol 或 runtime 构造出的端口对象。

禁止依赖：

- 禁止依赖 `api/routes`。
- 禁止依赖 `api/schemas` 作为内部领域模型。
- 禁止业务模块之间随意互相调用内部类。
- 禁止非 admin 模块依赖 `AdminService`。

### `modules/<domain>/repository.py`

职责：

- 集中本模块 SQL 读写。
- 返回 service 可理解的数据结构。

允许依赖：

- `db`
- SQLAlchemy
- `shared` 中的通用类型

禁止依赖：

- 禁止调用 route。
- 禁止构造 API response。
- 禁止调用外部 provider。
- 禁止做复杂权限决策；权限条件应由 service 或 permission helper 传入。

### `modules/<domain>/runtime.py`

职责：

- 基于 active config、secret、环境变量组装运行时依赖。
- 构造 adapter、provider、writer、reader 等外部依赖对象。

允许依赖：

- `modules/config`
- `modules/secrets`
- `adapters`
- `shared`

禁止依赖：

- 禁止处理 HTTP 入参。
- 禁止返回 API DTO。
- 禁止写业务状态，除非该 runtime 明确是 worker runtime 且文档说明。

### `shared`

职责：

- 放置无业务归属的公共错误、时间、ID、分页、日志、request_id 等工具。

允许依赖：

- 标准库。
- 极少数稳定第三方库。

禁止依赖：

- 禁止依赖 `modules/*`。
- 禁止依赖 `api/*`。
- 禁止包含业务权限规则。

### `adapters`

职责：

- 封装外部系统 SDK 或 HTTP 协议差异。
- 包括对象存储、向量库、模型 provider、rerank provider 等。

允许依赖：

- 外部 SDK。
- `shared` 的错误或基础类型。

禁止依赖：

- 禁止依赖 `api/*`。
- 禁止依赖业务 service。
- 禁止读取数据库。

### `db`

职责：

- 数据库连接、session、metadata、migration 相关能力。

禁止依赖：

- 禁止依赖 `api/*`。
- 禁止依赖 `modules/*`。

## 模块依赖方向

推荐方向：

```text
api/routes
  -> api/dependencies
  -> api/presenters
  -> api/schemas
  -> modules/<domain>/service facade
  -> modules/<domain>/repository
  -> shared / db / runtime
  -> adapters
```

更准确的运行时依赖：

```text
route -> service/facade -> repository -> db
route -> service/facade -> permission helper
service/facade -> runtime -> config/secrets/adapters
presenter -> schema
```

禁止方向：

```text
modules -> api/routes
modules -> api/schemas
shared -> modules
adapters -> modules
db -> modules
permissions route -> admin service
public schema <-> admin schema
```

## API 暴露边界

### 列表接口

必须满足：

- 后端分页：`page`、`page_size`、`total`。
- 后端筛选：`keyword`、`status`、`department_id`、`kb_id`、`date_range` 等。
- 后端权限过滤。
- 只返回列表展示字段。

禁止返回：

- 完整配置。
- 权限策略完整结构。
- 内部 hash。
- trace/request 内部 ID。
- 全文 chunk。
- prompt、文档原文。

### 详情接口

必须满足：

- 独立做权限检查。
- 不因为列表可见就默认详情可见。
- 只返回当前详情页需要的字段。

允许：

- 返回比列表更多的业务详情。
- 返回经过裁剪和脱敏后的诊断信息。

禁止：

- 默认返回 secret、token、provider key。
- 默认返回 prompt、文档全文、内部 hash。

## DTO 复用规则

允许：

- 复用 `api/schemas/common.py` 中的通用结构，例如分页、基础错误响应。
- 通过 presenter 复用内部字段映射逻辑。

禁止：

- admin API 直接复用 public response DTO。
- public API 直接复用 admin response DTO。
- 为减少重复而合并列表 DTO 和详情 DTO。

判断标准：

- 如果两个 DTO 的权限暴露边界不同，必须拆开。
- 如果两个 DTO 只是字段名称相同，但面向不同用户角色，也优先拆开。
- 如果只是分页、基础状态、简单 lookup item，可以放到 common。

## 权限边界

必须遵守：

- 权限过滤只能在后端完成。
- 前端隐藏菜单不算权限控制。
- 查询、详情、导入、索引重建、权限修改都必须在 service 层进行权限检查。
- 检索候选片段必须经过二次权限 gate，不能只依赖 Qdrant payload 过滤。

禁止：

- route 自行拼接权限 SQL。
- 前端传入的 department_id、kb_id 被默认信任。
- 管理后台可见就默认拥有详情权限或操作权限。

## Runtime 与外部依赖边界

必须遵守：

- 对象存储、模型 provider、向量库 writer/reader 由 runtime 统一构造。
- secret 只能在 runtime 或 secrets 模块读取。
- provider 调用必须保留认证 header、timeout、错误映射和审计上下文。

禁止：

- route 直接构造 MinIO/Qdrant/provider client。
- service 到处重复读取 active_config 和 secret。
- provider 重构时丢失 api key/header。

## 当前重点模块拆分目标

### `admin`

目标：

- 拆分用户、部门、角色、知识库、文档、索引运维、权限管理 service。
- 拆分 admin route。
- 抽离 presenter。

特殊约束：

- admin 可以看到更多管理字段，但不能默认看到所有内部字段。
- 权限策略修改必须调用 permissions 模块的管理侧能力。

### `permissions`

目标：

- 拆分 context loader、filter builder、policy validator、candidate gate。
- 解除 permissions route 对 AdminService 的依赖。

特殊约束：

- 权限逻辑是后端安全边界，不允许下沉到前端。

### `query`

目标：

- 拆分 retrieval pipeline、citation validator、degrade policy、repository、log writer。

特殊约束：

- RAG 查询可以只基于当前问题检索，但多轮历史可以作为 answer prompt 上下文。
- 无结果、低相关、provider 异常、citation 异常都必须给用户可解释回答。

### `config`

目标：

- 拆分 reader、version service、publisher、dependency validator、repository。

特殊约束：

- active_config 读取侧不能被配置版本管理复杂度污染。
- 配置新建、编辑、初始化必须复用同一校验规则。

### `import_pipeline`

目标：

- 拆分 command service、worker service、stage runner、document writer、permission guard、repository。

特殊约束：

- API 创建导入任务和 worker 推进状态机必须分离。
- 导入权限和 owner_department 校验必须后端执行。

### `indexing`

目标：

- 拆分 target repository、draft service、publish service、cleanup service、permission payload service。

特殊约束：

- 导入发布、重建索引、权限刷新、pending delete 清理互相隔离。
- Qdrant 运维能力保留在 ops service，不混入主索引发布流程。

### `setup`

目标：

- 拆分 payload validator、secret initializer、organization initializer、config publisher、recovery service、repository。

特殊约束：

- 初始化失败不能写入半成品 active_config。
- recovery setup 与首次 setup 使用同一状态边界。

## Review 检查清单

每次后端重构提交前检查：

- route 是否仍存在重复 `_authenticate`、`_extract_bearer_token`、`_request_id`。
- route 是否直接构造外部 adapter。
- route 是否直接读取 secret。
- route 是否直接写复杂 SQL。
- module 是否依赖了 `api/schemas`。
- public/admin DTO 是否发生交叉复用。
- 列表接口是否返回详情字段。
- 详情接口是否独立做权限检查。
- 权限过滤是否完全由后端完成。
- provider 调用是否保留 key/header/timeout/error mapping。
- 新增 service 是否有清晰 repository/runtime/presenter 边界。

## 验证要求

结构重构至少执行：

- 受影响模块单元测试。
- 受影响接口 smoke 测试。
- `ruff check`。
- 若 API response 变化，执行对应前端 build。

高风险场景必须额外覆盖：

- 系统管理员、部门管理员、知识库管理员、普通员工四类账号权限。
- 401、403、404、409、428、500 错误响应。
- 导入、索引重建、权限刷新、查询降级、citation 校验。
