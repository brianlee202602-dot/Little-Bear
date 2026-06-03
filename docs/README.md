# Little Bear 当前项目文档

本目录用于存放已经过实现校对、可以作为团队后续开发依据的成熟文档，包括架构设计、功能说明、接口约束、开发规范和运维说明。

## 当前文档

- [项目总体架构设计书](architecture/项目总体架构设计书.md)
- [核心业务链路时序图](architecture/核心业务链路时序图.md)
- [本地开发环境说明](development/本地开发环境说明.md)
- [后端架构设计书](backend/后端架构设计书.md)
- [后端接口文档](backend/后端接口文档.md)
- [后端模块职责索引](backend/后端模块职责索引.md)
- [领域模型与数据关系说明](backend/领域模型与数据关系说明.md)
- [权限模型设计书](backend/权限模型设计书.md)
- [安全边界与威胁模型](backend/安全边界与威胁模型.md)
- [RAG 查询链路实现说明](backend/RAG查询链路实现说明.md)
- [导入与索引生命周期说明](backend/导入与索引生命周期说明.md)
- [模型 Provider 接入说明](backend/模型Provider接入说明.md)
- [配置与 Secret 运行时说明](backend/配置与Secret运行时说明.md)
- [降级策略与错误码说明](backend/降级策略与错误码说明.md)
- [可观测性与诊断说明](backend/可观测性与诊断说明.md)
- [数据库迁移与版本管理说明](backend/数据库迁移与版本管理说明.md)
- [缓存设计说明](backend/缓存设计说明.md)
- [既有文档元数据补齐策略](backend/既有文档元数据补齐策略.md)
- [部署与运行手册](operations/部署与运行手册.md)
- [生产部署拓扑说明](operations/生产部署拓扑说明.md)
- [备份与恢复说明](operations/备份与恢复说明.md)
- [配置变更操作手册](operations/配置变更操作手册.md)
- [测试与验收策略](testing/测试与验收策略.md)
- [模型与检索评测基线](testing/模型与检索评测基线.md)
- [管理后台前端架构设计书](frontend/管理后台前端架构设计书.md)
- [管理后台功能与交互说明](frontend/管理后台功能与交互说明.md)
- [查询前端架构设计书](frontend/查询前端架构设计书.md)
- [前后端交互约束说明](frontend/前后端交互约束说明.md)
- [工程契约索引](contracts/README.md)
- [OpenAPI 契约](contracts/openapi.yaml)
- [配置 Schema](contracts/config.schema.json)
- [配置 Schema 说明](contracts/config-schema.md)
- [数据库 Schema](contracts/database-schema.md)
- [权限矩阵](contracts/权限矩阵.md)
- [审计事件字典](contracts/审计事件字典.md)
- [状态机设计](contracts/状态机设计.md)
- [P0 查询回归样例](examples/query-regression.p0.jsonl)
- [RAG 增强查询回归样例](examples/query-regression.rag-enhancement.jsonl)
- [本地初始化样例](examples/setup-initialization.local.p0.json)

## 目录规划

- `architecture/`：项目总体架构、核心链路、组件边界和时序图。
- `development/`：本地开发环境、启动顺序、调试入口和常见故障。
- `frontend/`：普通查询前端、管理后台前端和共享前端能力的架构设计与开发约束。
- `backend/`：后端模块边界、服务编排、运行时、权限、安全和错误处理等成熟设计文档。
- `contracts/`：OpenAPI、权限矩阵、状态机、审计事件、配置 Schema 等稳定契约。
- `operations/`：部署、发布、备份、恢复、告警和生产运维操作手册。
- `testing/`：验收标准、测试计划、回归用例和真实联调记录。
- `examples/`：初始化、smoke、查询回归和评测相关的可执行样例数据。

以上目录按需创建；未完成实现校对的文档不要提前迁入本目录。
