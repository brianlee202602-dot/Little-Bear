"""FastAPI 应用装配入口。

这里只负责把全局中间件、路由和启动检查串起来。真正的业务初始化判断放在
SetupStartupService，避免业务模块在导入阶段就触碰数据库或外部依赖。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, health, setup
from app.modules.setup.startup_service import SetupStartupService
from app.shared.logging import configure_logging
from app.shared.middleware import RequestContextMiddleware, SetupGuardMiddleware
from app.shared.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # 测试可以关闭启动检查；真实进程启动时必须先确认数据库和 setup 状态。
    if getattr(app.state, "run_startup_checks", True):
        SetupStartupService().run()
    yield


def create_app(*, run_startup_checks: bool = True) -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Little Bear API",
        version="0.1.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        lifespan=lifespan,
    )
    app.state.run_startup_checks = run_startup_checks
    # RequestContext 先写入 request_id/trace_id，SetupGuard 再基于初始化状态放行或拒绝。
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SetupGuardMiddleware)
    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(setup.router)
    return app


app = create_app()
