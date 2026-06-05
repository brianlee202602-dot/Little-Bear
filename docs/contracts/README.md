# Little Bear 工程契约索引

本目录存放交付版成熟工程契约。后端运行时、契约测试、前端 DTO、权限校验和审计设计应引用本目录。

## 契约文件

- [OpenAPI 契约](openapi.yaml)：HTTP 接口路径、方法、请求响应 DTO、阶段标记和 API contract 测试依据。
- [配置 Schema](config.schema.json)：setup payload 与 active config 的机器校验 Schema。
- [配置 Schema 说明](config-schema.md)：配置字段语义、校验意图和运行约束。
- [数据库 Schema](database-schema.md)：PostgreSQL 事实源表结构、索引、状态字段和关键约束说明。
- [权限矩阵](权限矩阵.md)：接口级鉴权类型、scope、资源校验和高风险确认要求。
- [审计事件字典](审计事件字典.md)：审计事件、风险等级、脱敏字段和写入场景。
- [状态机设计](状态机设计.md)：setup、配置、导入、索引、文档、权限和查询等核心状态流转。

## 维护要求

- API 非兼容变更必须同步更新 `openapi.yaml`、权限矩阵、审计事件字典和相关测试。
- 配置字段变更必须同步更新 `config.schema.json` 和 `config-schema.md`。
- 数据库迁移涉及事实源结构或状态字段时，必须同步更新 `database-schema.md` 和状态机设计。
- 前端 DTO、后端 `api/schemas`、OpenAPI 和接口文档必须保持字段命名一致。
