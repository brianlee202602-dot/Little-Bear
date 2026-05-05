# RAG 后端设计文档索引

本目录是企业内部高并发生产级 RAG 检索系统的工程设计文档集，用于指导后续代码实现、评审、测试和上线。

## 阅读顺序

1. [架构设计文档](架构设计文档.md)
2. [MVP 范围说明](MVP范围说明.md)
3. [公共实现约束](modules/00-公共实现约束.md)
4. [核心数据模型](modules/14-核心数据模型设计实现文档.md)
5. [项目执行流程图](项目执行流程图.md)
6. [正式编码前任务追踪](planning/正式编码前任务追踪.md)
7. 按模块阅读 `docs/modules/` 下的实现设计文档

## 文档清单

| 文档 | 内容 |
| --- | --- |
| [架构设计文档.md](架构设计文档.md) | 总体架构、部署拓扑、关键链路、状态流转、演进路线 |
| [MVP范围说明.md](MVP范围说明.md) | 第一阶段 MVP 闭环、P0 功能范围、暂不实现范围、成功标准和验收路径 |
| [项目执行流程图.md](项目执行流程图.md) | 项目总执行流程图、各功能模块流程图、关键执行约束 |
| [planning/正式编码前任务追踪.md](planning/正式编码前任务追踪.md) | 编码前 P0/P1 任务追踪、准入标准、风险清单 |

## 工程契约

| 文档 | 内容 |
| --- | --- |
| [contracts/openapi.yaml](contracts/openapi.yaml) | REST API、错误结构、鉴权声明和响应 schema |
| [contracts/config.schema.json](contracts/config.schema.json) | 初始化配置和 active config 的机器可校验 JSON Schema |
| [contracts/config-schema.md](contracts/config-schema.md) | 初始化配置和 active config 字段语义 |
| [contracts/database-schema.md](contracts/database-schema.md) | PostgreSQL 事实源 schema、索引和 migration 草案 |
| [contracts/权限矩阵.md](contracts/权限矩阵.md) | endpoint 级权限、确认和补偿策略 |
| [contracts/状态机设计.md](contracts/状态机设计.md) | P0 核心状态机、迁移、重试和补偿策略 |
| [contracts/审计事件字典.md](contracts/审计事件字典.md) | P0 审计事件、summary_json 和脱敏规则 |

## 执行与验收

| 文档 | 内容 |
| --- | --- |
| [testing/测试计划.md](testing/测试计划.md) | P0 自动化测试、CI 门禁和验收边界 |
| [development/本地开发环境.md](development/本地开发环境.md) | 本地依赖启动、初始化和 P0 验收路径 |
| [admin/管理后台交互契约.md](admin/管理后台交互契约.md) | 管理后台路由、菜单、表单、确认和审计展示 |
| [operations/安装部署操作手册.md](operations/安装部署操作手册.md) | 安装依赖、启动基础设施、执行迁移、写入 Secret 和首次初始化操作步骤 |
| [operations/配置变更与热更新策略.md](operations/配置变更与热更新策略.md) | 配置 diff、风险、热更新、失败和阶段 2 回滚边界 |
| [operations/部署与发布检查清单.md](operations/部署与发布检查清单.md) | migration、备份恢复、发布演练和 Go / No-Go 条件 |
| [observability/审计查询与展示扩展.md](observability/审计查询与展示扩展.md) | 审计查询、展示、导出、retention 和脱敏扩展 |
| [evaluation/模型与检索评测基线.md](evaluation/模型与检索评测基线.md) | 检索、citation、拒答、延迟和成本评测基线 |

## 模块设计

| 文档 | 内容 |
| --- | --- |
| [00-公共实现约束.md](modules/00-公共实现约束.md) | 代码分层、依赖方向、事务、错误、配置、测试规范 |
| [01-初始化服务设计实现文档.md](modules/01-初始化服务设计实现文档.md) | 首次初始化、临时 system token、初始化状态机 |
| [02-认证服务设计实现文档.md](modules/02-认证服务设计实现文档.md) | 本地账号、登录、会话/JWT、服务端鉴权 |
| [03-组织服务设计实现文档.md](modules/03-组织服务设计实现文档.md) | 企业、部门、成员组织关系 |
| [04-权限服务设计实现文档.md](modules/04-权限服务设计实现文档.md) | RBAC、部门/企业可见性、权限上下文、权限过滤下推 |
| [05-配置服务设计实现文档.md](modules/05-配置服务设计实现文档.md) | active config、配置草稿、发布、回滚、热更新 |
| [06-导入服务与工作进程设计实现文档.md](modules/06-导入服务与工作进程设计实现文档.md) | 文档导入 API、任务状态机、轻量 Worker |
| [07-索引服务设计实现文档.md](modules/07-索引服务设计实现文档.md) | 向量索引、关键词索引、索引版本、发布与回滚 |
| [08-查询服务设计实现文档.md](modules/08-查询服务设计实现文档.md) | 查询 API、请求上下文、限流、流式响应 |
| [09-检索上下文与答案生成设计实现文档.md](modules/09-检索上下文与答案生成设计实现文档.md) | rewrite、召回、融合、rerank、上下文、答案生成 |
| [10-模型网关设计实现文档.md](modules/10-模型网关设计实现文档.md) | Embedding、Rerank、LLM 统一 Provider Adapter |
| [11-审计与可观测性设计实现文档.md](modules/11-审计与可观测性设计实现文档.md) | 日志、审计、指标、Trace、质量评测 |
| [12-接口网关与高并发设计实现文档.md](modules/12-接口网关与高并发设计实现文档.md) | 请求入口、限流、超时、降级、缓存 |
| [13-部署与运维设计实现文档.md](modules/13-部署与运维设计实现文档.md) | Docker Compose 部署、容量规划、备份、上线检查 |
| [14-核心数据模型设计实现文档.md](modules/14-核心数据模型设计实现文档.md) | 知识库、文档、chunk、权限快照、索引版本、删除阻断、查询缓存 |
| [15-前端与管理后台API设计实现文档.md](modules/15-前端与管理后台API设计实现文档.md) | 普通前端、管理后台、初始化、运维和内部服务 API 边界 |

## 归档与示例

| 路径 | 内容 |
| --- | --- |
| [archive/企业内部高并发生产级RAG检索系统后端设计.md](archive/企业内部高并发生产级RAG检索系统后端设计.md) | 原始总设计文档归档 |
| [examples/setup-initialization.local.p0.json](examples/setup-initialization.local.p0.json) | 本地 P0 初始化 payload 示例 |
| [examples/eval-dataset.local.p1.jsonl](examples/eval-dataset.local.p1.jsonl) | P1 本地评测 smoke 数据集 |

## 实施约定

- 最小生产阶段采用模块化单体 + 轻量导入 Worker。
- API、Worker 和模型 Provider Adapter 进程的启动配置只包含数据库连接内容，业务配置全部来自初始化接口发布后的 active config。
- Redis、Secret Provider、MinIO、Qdrant、模型服务和业务策略都从数据库 active config 读取。
- 未初始化时只开放 setup 状态和初始化接口，普通业务 API 必须返回 `SETUP_REQUIRED`。
- 权限过滤必须下推到向量检索和关键词检索，禁止全量召回后再做应用层过滤。
- 查询候选进入上下文前仍必须执行元数据可见性、access block 和引用有效性准入校验，作为索引权限字段的兜底校验。
- 查询结果缓存默认按用户和权限过滤条件隔离，禁止跨租户、跨权限上下文复用。
- 所有模块都通过 ports/interfaces 访问外部依赖，具体实现放在 adapters。
- 所有关键操作必须记录 `request_id`、`trace_id`、`user_id`、`config_version` 和必要审计字段。
