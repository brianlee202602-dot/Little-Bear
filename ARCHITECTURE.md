# Little Bear 架构总览

更新时间：2026-06-03

本文是根目录架构入口，用于帮助开发者和自动化编码代理快速理解 Little Bear 的系统边界、组件关系和核心链路。详细设计以 `docs/` 下成熟文档为准，本文只做架构地图，不重复展开所有实现细节。

## 1. 项目定位

Little Bear 是面向企业内部知识检索与问答的 RAG 系统。核心目标是：

- 用户只能检索自己有权限访问的知识库和文档。
- 文档导入、索引发布、权限变化、模型服务波动和复杂查询都可审计、可降级、可恢复。
- PostgreSQL 作为业务事实源，MinIO、Qdrant、Redis 和模型 provider 作为外部依赖或派生运行能力。

## 2. 工作区结构

```text
apps/api        FastAPI API 服务
apps/worker     文档导入、解析、切块、embedding 和索引发布 Worker
apps/web        普通用户查询前端
apps/admin      管理后台前端
packages/       共享契约、前端 SDK 和共享 UI 包
docs/           交付版项目文档
tests/          单元、集成、契约和回归测试
```

## 3. 技术栈概要

后端：

- Python `>=3.12`
- FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings
- SQLAlchemy 2.x + Alembic
- PostgreSQL + `psycopg[binary]`
- PyJWT
- argon2-cffi
- MinIO / S3-compatible object storage
- Qdrant

前端：

- npm workspaces
- Vue 3 + TypeScript
- Vite
- `vue-tsc`

基础设施：

- PostgreSQL：业务事实源。
- Redis：作为 ServiceBootstrap 依赖接入，业务缓存不属于交付版运行闭环。
- MinIO：对象存储。
- Qdrant：向量索引。
- embedding / rerank / LLM provider：由 active config 指定。

## 4. 组件关系

```text
普通用户
  -> apps/web
      -> apps/api
          -> PostgreSQL
          -> MinIO
          -> Qdrant
          -> Redis
          -> embedding / rerank / LLM provider

管理员
  -> apps/admin
      -> apps/api
          -> PostgreSQL
          -> MinIO
          -> Qdrant
          -> Redis

apps/worker
  -> PostgreSQL
  -> MinIO
  -> Qdrant
  -> embedding provider
```

API 处理 HTTP 请求、认证、管理和查询。Worker 不处理 HTTP 请求，只消费 PostgreSQL 中的导入任务并推进导入索引生命周期。

## 5. 后端依赖方向

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

职责边界详见：

- [后端架构设计书](docs/backend/后端架构设计书.md)
- [前后端交互约束说明](docs/frontend/前后端交互约束说明.md)

## 6. 配置与初始化架构

启动层只读取数据库连接、进程参数和 Secret Store 主密钥等最小参数。业务配置由数据库 active config 驱动。

当前规则：

- `.env` 不承载业务决策配置。
- active config 管理 Redis、MinIO、Qdrant、embedding、rerank、LLM、检索策略、权限策略、超时、降级、审计等运行配置。
- Secret Store 保存 MinIO、JWT、模型 provider 等敏感值。
- ServiceBootstrap 校验 active config、secret、Redis、MinIO、Qdrant、关键词检索和模型 provider。

详细说明见：

- [配置与 Secret 运行时说明](docs/backend/配置与Secret运行时说明.md)
- [部署与运行手册](docs/operations/部署与运行手册.md)

## 7. 权限架构

权限由 RBAC scope、部门作用域、知识库作用域、知识库可见性和文档可见性共同构成。

关键原则：

- 前端隐藏菜单不是权限边界。
- 知识库可见不等于知识库内所有文档可见。
- 查询候选进入上下文前必须经过权限和状态过滤。
- deleted、blocked、draft、archived、access block 命中的内容不得进入查询上下文。
- citation source 读取必须重新鉴权。

详细说明见：

- [权限模型设计书](docs/backend/权限模型设计书.md)
- [权限矩阵](docs/contracts/权限矩阵.md)

## 8. 导入与索引链路

核心链路：

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

详细说明见：

- [导入与索引生命周期说明](docs/backend/导入与索引生命周期说明.md)
- [核心业务链路时序图](docs/architecture/核心业务链路时序图.md)

## 9. RAG 查询链路

当前查询链路包括：

```text
鉴权
-> Permission Service 构建权限上下文
-> 服务端解析可访问知识库范围
-> Query Rewrite / 联合问题拆分
-> 关键词召回 + 向量召回
-> Weighted RRF 融合
-> rerank
-> Candidate Quality Gate
-> embedding MMR 去冗余
-> 相邻 chunk 扩展
-> Context Builder
-> LLM 生成
-> citation 校验与自动修复
-> query_logs / model_call_logs / audit / retrieval diagnostics
```

详细说明见：

- [RAG 查询链路实现说明](docs/backend/RAG查询链路实现说明.md)
- [降级策略与错误码说明](docs/backend/降级策略与错误码说明.md)
- [可观测性与诊断说明](docs/backend/可观测性与诊断说明.md)

## 10. 前端架构

普通查询前端和管理后台均采用 Vue 3 Composition API。API 调用集中在各应用 `src/api` 下，组件不散落拼接后端 URL。

详细说明见：

- [查询前端架构设计书](docs/frontend/查询前端架构设计书.md)
- [管理后台前端架构设计书](docs/frontend/管理后台前端架构设计书.md)
- [前后端交互约束说明](docs/frontend/前后端交互约束说明.md)

## 11. 交付边界

- Redis 已作为基础设施和 ServiceBootstrap 依赖接入，业务缓存不属于交付版运行闭环。
- 最终答案缓存不属于交付版运行链路。
- 生产拓扑说明不等于已有 Kubernetes / Helm 编排。
- 查询多轮会话已保存和展示，不包含长历史总结或跨轮意图规划。
- 交付版项目文档存放在 `docs/`；根目录计划类文档不应替代实现校对后的成熟文档。

## 12. 架构文档入口

- [项目总体架构设计书](docs/architecture/项目总体架构设计书.md)
- [核心业务链路时序图](docs/architecture/核心业务链路时序图.md)
- [后端架构设计书](docs/backend/后端架构设计书.md)
- [后端接口文档](docs/backend/后端接口文档.md)
- [领域模型与数据关系说明](docs/backend/领域模型与数据关系说明.md)
- [权限模型设计书](docs/backend/权限模型设计书.md)
- [RAG 查询链路实现说明](docs/backend/RAG查询链路实现说明.md)
- [导入与索引生命周期说明](docs/backend/导入与索引生命周期说明.md)
- [管理后台前端架构设计书](docs/frontend/管理后台前端架构设计书.md)
- [查询前端架构设计书](docs/frontend/查询前端架构设计书.md)
