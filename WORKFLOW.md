# Little Bear 开发工作流

更新时间：2026-06-03

本文说明 Little Bear 的开发、测试、文档同步和验收流程。自动化编码代理执行任务时，应以本文作为流程入口；架构地图见 [ARCHITECTURE.md](ARCHITECTURE.md)，代理行为规则见 [AGENTS.md](AGENTS.md)。

## 1. 基本原则

- 修改前先明确任务目标、影响范围、成功标准和风险边界。
- 优先使用 `Makefile` 和 package scripts 中已有命令。
- 不绕过后端权限、状态、citation 和 ServiceBootstrap 边界。
- 不把未实现能力写成已实现能力。
- 不修改与当前任务无关的脏文件。
- 代码、测试、OpenAPI、权限矩阵、状态机、审计字典和前端 DTO 必须保持一致。

## 2. 常用命令

本地基础设施：

```bash
make env
make up
make ps
make logs
make down
make reset
```

数据库迁移：

```bash
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python db-current
```

启动进程：

```bash
make PYTHON=.venv/bin/python api
make PYTHON=.venv/bin/python worker
make web
make admin
```

测试和验收：

```bash
make PYTHON=.venv/bin/python test
make PYTHON=.venv/bin/python test-integration-qdrant
make PYTHON=.venv/bin/python smoke-p0
make PYTHON=.venv/bin/python query-regression-p0
make PYTHON=.venv/bin/python query-regression-rag
make PYTHON=.venv/bin/python release-smoke-p0
npm run typecheck:web
npm run typecheck:admin
npm run build:web
npm run build:admin
```

## 3. 通用开发流程

1. 查看 `git status --short`，确认工作区脏文件。
2. 阅读当前任务相关的 `docs/` 成熟文档和代码。
3. 派生明确的验收项。
4. 只修改任务相关文件。
5. 按变更类型运行测试或校验。
6. 同步更新 README、docs 索引、契约或计划清单。
7. 输出修改摘要、测试结果和剩余风险。

## 4. 后端变更流程

适用场景：

- `apps/api`
- `apps/worker`
- `tests`
- Alembic migration
- 后端契约文档

流程：

1. 根据 [ARCHITECTURE.md](ARCHITECTURE.md) 确认模块边界。
2. route 只处理 HTTP 入参、认证、分页、状态码和错误映射。
3. service / facade 负责业务编排和事务边界。
4. repository 负责 SQL 读写。
5. runtime 负责 active config、secret 和外部 adapter 组装。
6. presenter 负责展示字段裁剪。
7. 新增或修改 API 时同步 schema、presenter、service、错误码、scope、OpenAPI、前端 API client 和测试。

最低门禁：

```bash
make PYTHON=.venv/bin/python test
```

涉及 Qdrant、embedding、索引发布或重建索引时追加：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

## 5. 前端变更流程

适用场景：

- `apps/web`
- `apps/admin`
- `packages/frontend-sdk`
- `packages/ui`

流程：

1. API 调用集中在 `src/api/<domain>.ts` 或共享 SDK。
2. DTO 字段保持后端契约原名，不在 API 层改 camelCase。
3. 列表页使用后端分页、筛选和权限过滤。
4. 详情页调用详情接口，不通过列表过量返回数据。
5. 认证统一使用 `Authorization: Bearer <jwt>`。
6. 错误展示使用后端结构化错误中的 `error_code`、`message`、`request_id` 或 `debug_id`。

普通查询前端门禁：

```bash
npm run typecheck:web
npm run build:web
```

管理后台门禁：

```bash
npm run typecheck:admin
npm run build:admin
```

两个前端应用共享契约变更时，两个应用都要验证。

## 6. API 与契约变更流程

API 非兼容变更必须同步：

- 后端 route / schema / presenter / service。
- `docs/contracts/openapi.yaml`。
- `docs/contracts/权限矩阵.md`。
- `docs/contracts/审计事件字典.md`。
- 前端 API client / SDK / DTO。
- 对应测试。

列表接口必须满足：

- 后端分页：`page`、`page_size`、`total`。
- 后端筛选：如 `keyword`、`status`、`department_id`、`kb_id`、`date_range`。
- 后端权限过滤。
- 只返回列表展示字段。

详情接口必须重新鉴权。

## 7. 数据库迁移流程

适用场景：

- 新增表。
- 新增字段。
- 新增索引。
- 新增约束。
- 状态枚举变化。
- 数据回填。

流程：

1. 追加新的 Alembic migration，不修改已发布 migration 的业务语义。
2. 在 migration 中表达数据库约束、外键、唯一索引、CHECK 和必要回填。
3. 更新 ORM / repository / schema / service。
4. 更新数据库契约和相关文档。
5. 执行迁移验收。

门禁：

```bash
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python db-current
make PYTHON=.venv/bin/python test
```

详细说明见：

- [数据库迁移与版本管理说明](docs/backend/数据库迁移与版本管理说明.md)

## 8. RAG 变更流程

适用场景：

- Query Rewrite。
- 服务端知识库范围解析。
- 关键词召回。
- 向量召回。
- fusion。
- rerank。
- candidate gate。
- Context Builder。
- LLM 调用。
- citation 校验。
- 降级策略。

流程：

1. 明确变更影响的是召回、排序、上下文、生成、引用还是降级。
2. 保留权限过滤和 access block fail closed。
3. 保留 citation 校验，不返回未授权 source。
4. 更新或新增查询回归样例。
5. 检查 query log、model call log 和 retrieval diagnostics。

门禁：

```bash
make PYTHON=.venv/bin/python test
make PYTHON=.venv/bin/python query-regression-rag
```

涉及 Qdrant 或 embedding 时追加：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

## 9. 权限变更流程

涉及以下内容时按高风险处理：

- RBAC scope。
- 角色绑定。
- 部门作用域。
- 知识库可见性。
- 文档可见性。
- access block。
- source 读取。
- citation 校验。

必须覆盖：

- 普通用户调用管理员接口被拒绝。
- 跨部门文档不可查询。
- 文档权限收紧后旧索引不可继续命中。
- deleted document 不可查询。
- blocked document 不可查询。
- draft index 不可查询。
- archived index 不可查询。
- source 详情读取重新鉴权。
- citation unauthorized 抑制原答案。

最低门禁：

```bash
make PYTHON=.venv/bin/python test
```

## 10. 文档变更流程

文档变更必须基于当前实现，不写计划能力为已实现。

成熟文档放在：

```text
docs/
```

根目录计划、清单和执行记录可以保留在根目录，但不能替代 `docs/` 中的成熟文档。

文档任务验收：

```bash
rg -n "历史设计|旧架构|旧模块|旧契约" README.md docs || true
```

同时检查 README 和 `docs/README.md` 链接是否指向真实文件。

## 11. 发布前验收

发布候选至少运行：

```bash
make PYTHON=.venv/bin/python release-smoke-p0
npm run build:web
npm run build:admin
```

涉及索引、Qdrant 或 embedding 变更时追加：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

涉及 RAG 行为变更时追加：

```bash
make PYTHON=.venv/bin/python query-regression-rag
```

## 12. 故障排查入口

- 登录或接口返回 `SERVICE_BOOTSTRAP_UNAVAILABLE`：看 [配置与 Secret 运行时说明](docs/backend/配置与Secret运行时说明.md)。
- 查询降级或 citation 异常：看 [降级策略与错误码说明](docs/backend/降级策略与错误码说明.md)。
- 查询无答案或相关性异常：看 [RAG 查询链路实现说明](docs/backend/RAG查询链路实现说明.md)。
- 导入任务失败：看 [导入与索引生命周期说明](docs/backend/导入与索引生命周期说明.md)。
- 索引健康异常：看 [可观测性与诊断说明](docs/backend/可观测性与诊断说明.md)。
- 前后端字段或分页异常：看 [前后端交互约束说明](docs/frontend/前后端交互约束说明.md)。

## 13. 禁止事项

- 不用前端菜单隐藏替代后端权限。
- 不用 `.env` 承载业务配置。
- 不把 secret value、token、密码、完整 prompt 或文档原文写入日志和文档。
- 不直接修改已发布 migration 的业务语义。
- 不为了快速通过测试而放宽权限、citation 或索引可见性约束。
- 不把 Redis 描述为已实现业务缓存，除非代码中已有真实读写路径。
