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

当前 `Makefile` 保留基础设施生命周期、FastAPI 主程序和前端开发入口：

```bash
make api
make web
make admin
```

其中 `make api` 使用 `uvicorn` 启动 FastAPI ASGI 应用：

```bash
PYTHONPATH=apps/api python3 -m uvicorn app.main:app --host ${API_HOST:-0.0.0.0} --port ${API_PORT:-8000} --reload
```

数据库迁移已收敛到 `Makefile`；Worker 等命令需要时仍可直接使用原生命令，例如：

```bash
make PYTHON=python3 db-upgrade
python3 apps/worker/app/main.py
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
- 管理后台已接入 setup、登录、配置、用户、部门、角色绑定和审计查询。
- RAG 数据面仍待补齐：Permission Service 核心已落地但尚未接入业务 API；知识库/文档完整管理、导入 Worker、索引发布、查询检索、答案生成和 citation 校验仍待实现。
- 当前开发进度详见根目录 `开发进度追踪.md`。

建议下一步按以下顺序推进：

1. 持续保持实际 FastAPI routes 与 `docs/contracts/openapi.yaml` 的契约对齐。
2. 将 `Permission Service` 接入后续知识库、文档、导入和查询 API。
3. 补齐知识库、文件夹、文档和权限变更 API。
4. 实现 Import Service 与 Worker claim loop。
5. 实现 Indexing Service 和 active index 发布。
6. 实现非流式查询闭环，再补流式查询和普通用户前端。
