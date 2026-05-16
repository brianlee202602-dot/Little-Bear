# Little Bear

Little Bear 是一个面向企业内部知识检索与问答场景的 RAG 系统工作区。当前仓库已整理设计文档，并搭好了后端 API、Worker、Vue3 普通前端和 Vue3 管理后台的最小骨架。

## 目录结构

```text
apps/
  api/            FastAPI API
  worker/         导入与索引 Worker
  web/            Vue3 普通前端
  admin/          Vue3 管理后台

packages/
  shared-contracts/
  frontend-sdk/
  ui/

infra/
tests/
docs/
```

## 现有基础设施

仓库保留了本地开发依赖：

- PostgreSQL
- Redis
- MinIO
- Qdrant
- 本地演示用 TEI embedding / TEI rerank；实际可接入外部 provider 后删除对应 compose service

基础设施当前通过 `Makefile` 封装 Docker Compose 启动：

```bash
make env
make up
make ps
```

PostgreSQL 容器健康后，需要先执行 Alembic 迁移初始化数据库结构。迁移必须在安装了项目 Python 依赖的环境中执行，并且从仓库根目录运行：

```bash
python3 -m alembic.config --version
make PYTHON=python3 db-upgrade
make PYTHON=python3 db-current
```

如果 `python3 -m alembic.config --version` 提示找不到 `alembic`，说明当前解释器不是项目开发环境，需要先激活 venv/conda 环境或显式使用对应环境里的 Python。

## 本地开发入口

当前项目建议通过 `Makefile` 启动。`.env` 只作为本地进程环境来源，不要把真实业务密钥写入 README 或 Makefile。

首次启动先生成本地环境文件并拉起基础设施：

```bash
make env
make up
make ps
```

PostgreSQL 就绪后执行数据库迁移：

```bash
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python db-current
```

启动 API：

```bash
make PYTHON=.venv/bin/python api
```

`make api` 会读取 `$(ENV_FILE)`，默认是 `.env`，并以 reload 模式启动 FastAPI：

```bash
PYTHONPATH=apps/api LOG_LEVEL=INFO .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

启动导入与索引 Worker：

```bash
make PYTHON=.venv/bin/python worker
```

Worker 不处理 HTTP 请求，它负责消费 `import_jobs`，推进文档导入、解析、切块、embedding、Qdrant 写入和索引发布。上传文档后如果没有启动 Worker，任务会停留在 `queued`。

本地调试多个 Worker 时，不要把 `WORKER_ID` 写死在 `.env`，应在启动命令中为每个实例指定：

```bash
make PYTHON=.venv/bin/python WORKER_ID=import-worker-1 worker
make PYTHON=.venv/bin/python WORKER_ID=import-worker-2 worker
```

也可以使用简写：

```bash
make PYTHON=.venv/bin/python worker-1
make PYTHON=.venv/bin/python worker-2
```

启动普通用户 Web 和管理后台：

```bash
make web
make admin
```

常用本地启动顺序：

```bash
make up
make PYTHON=.venv/bin/python db-upgrade
make PYTHON=.venv/bin/python api
make PYTHON=.venv/bin/python worker
make web
make admin
```

Qdrant 与 embedding provider 的真实写入/召回联调测试默认不随单元测试运行。启动本地 `qdrant` 和 `tei-embedding` 后，可执行：

```bash
make test-integration-qdrant
```

如果当前 shell 使用项目虚拟环境，可显式指定解释器：

```bash
make PYTHON=.venv/bin/python test-integration-qdrant
```

初始化并导入可查询知识库后，可以执行 P0 主链路 smoke，覆盖登录、知识库浏览、非流式查询和 SSE 查询。执行前需要在 `.env` 或命令行中配置 `LITTLE_BEAR_SMOKE_USERNAME` 和 `LITTLE_BEAR_SMOKE_PASSWORD`，并确保该用户至少能访问一个已发布索引的知识库：

```bash
LITTLE_BEAR_SMOKE_USERNAME=<username> \
LITTLE_BEAR_SMOKE_PASSWORD=<password> \
make PYTHON=.venv/bin/python smoke-p0
```

数据库迁移完成后再启动 API。空库完成迁移但尚未执行业务初始化时，`GET /internal/v1/setup-state` 应返回未初始化状态，随后才能进入 `setup-config-validations` 和 `setup-initialization` 流程。

## 开发约定

- 项目代码中的注释、docstring 和面向开发者的说明默认使用中文。
- 注释优先解释设计意图、权限边界、事务边界、幂等、降级和安全限制，不重复描述显而易见的代码行为。
- 错误码、API 字段、数据库字段、配置 key、scope、枚举值和第三方协议术语保持契约中的原始名称。

## 当前状态

- 设计文档和工程契约已收敛，包含 MVP、OpenAPI、数据库 Schema、权限矩阵、状态机、审计事件字典和测试计划。
- 后端控制面已初步落地：初始化、setup token、active config、Secret Store、认证会话、配置管理、用户/部门/角色绑定管理、审计查询和健康检查。
- 数据库迁移已覆盖 P0 大部分核心表：配置、认证、组织、权限、知识库、文档、索引、导入任务、审计、查询日志和模型调用日志。
- 管理后台已接入 setup、登录、配置、用户、部门、角色绑定、审计查询和知识库运营页面；知识库页面已支持知识库 CRUD、文件夹 CRUD、指定文件夹上传、文档列表、文档版本、chunk 预览以及知识库 / 文档权限变更。
- Permission Service 核心已落地；管理端知识库、文件夹和文档元数据管理已接入权限边界。
- 文档详情、文档版本、chunk 来源、普通用户文档预览，以及知识库 / 文档独立权限变更 API 已补齐。
- Import Service、Worker 和 Indexing Service 最小链路已落地：支持上传 / URL / metadata_batch 导入任务创建、任务查询、取消、重试、Worker claim、MinIO/S3 对象存储交接、PDF / DOCX / UTF-8 文本 / Markdown parse-clean-chunk、draft chunk 写入、PostgreSQL 关键词索引账本、Qdrant draft vector point 写入和 active index 发布。
- Query Service 非流式链路已落地：`POST /internal/v1/queries` 支持关键词召回、query embedding client、Qdrant VectorRetriever adapter、RRF 融合排序、rerank provider、Permission Service filter、候选 gate、Context Builder、LLM provider、citation 校验、query_logs、model_call_logs 和高风险 query audit 写入；rerank、LLM 不可用或 citation 校验失败时结构化降级。
- Query Stream 和普通用户查询工作区第一版已落地：支持 `POST /internal/v1/query-streams` SSE 输出、Web 登录、token refresh、知识库浏览、文档浏览、citation 来源跳转、流式/非流式查询、降级状态、request_id 和 trace_id 展示。
- 已新增 P0 主链路 smoke 脚本和 `make smoke-p0` 入口；`employee` 内置角色已补齐 `knowledge_base:read` 初始化模板和存量迁移。
- RAG 数据面仍待补齐：复杂版式 / OCR 解析、查询改写、真实模型 token 级流式输出和真实业务回归数据集验证仍待实现。
- 当前开发进度详见根目录 `开发进度追踪.md`。

建议下一步按以下顺序推进：

1. 持续保持实际 FastAPI routes 与 `docs/contracts/openapi.yaml` 的契约对齐。
2. 增加真实 MinIO + Worker + API 联调记录、查询回归数据集与 P0 smoke 真实环境执行记录。
3. 将 Query Stream 从服务端缓冲式 SSE 升级为 provider token 级流式输出。
