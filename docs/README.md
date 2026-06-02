# Little Bear 当前项目文档

本目录用于存放已经过实现校对、可以作为团队后续开发依据的成熟文档，包括架构设计、功能说明、接口约束、开发规范和运维说明。

历史阶段的设计草稿、模块计划、联调记录和旧契约文档已整体归档到根目录 `design_docs_history/`。除非明确是在追溯历史决策，否则后续新增或更新文档应优先放入本目录。

## 当前文档

- [后端架构设计书](backend/后端架构设计书.md)
- [后端接口文档](backend/后端接口文档.md)
- [管理后台前端架构设计书](frontend/管理后台前端架构设计书.md)
- [查询前端架构设计书](frontend/查询前端架构设计书.md)
- [工程契约索引](contracts/README.md)
- [OpenAPI 契约](contracts/openapi.yaml)
- [配置 Schema](contracts/config.schema.json)
- [配置 Schema 说明](contracts/config-schema.md)
- [数据库 Schema](contracts/database-schema.md)
- [权限矩阵](contracts/权限矩阵.md)
- [审计事件字典](contracts/审计事件字典.md)
- [状态机设计](contracts/状态机设计.md)

## 目录规划

- `frontend/`：普通查询前端、管理后台前端和共享前端能力的架构设计与开发约束。
- `backend/`：后端模块边界、服务编排、运行时、权限、安全和错误处理等成熟设计文档。
- `contracts/`：OpenAPI、权限矩阵、状态机、审计事件、配置 Schema 等稳定契约。
- `operations/`：部署、发布、备份、恢复、告警和生产运维操作手册。
- `testing/`：验收标准、测试计划、回归用例和真实联调记录。

以上目录按需创建；未完成实现校对的文档不要提前迁入本目录。
