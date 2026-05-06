"""数据库启动健康检查。

Setup 启动阶段和 healthcheck 都会使用这里的轻量探测。它只判断数据库是否可连接，
不做业务初始化判断，避免把 setup 状态和基础连接状态混在一起。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_engine
from app.shared.settings import get_settings


@dataclass(frozen=True)
class DatabaseHealth:
    configured: bool
    reachable: bool
    error: str | None = None


def check_database() -> DatabaseHealth:
    settings = get_settings()
    if not settings.database_url:
        return DatabaseHealth(
            configured=False,
            reachable=False,
            error="DATABASE_URL is not configured",
        )

    try:
        with get_engine().connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        return DatabaseHealth(configured=True, reachable=False, error=exc.__class__.__name__)
    except Exception as exc:
        # 驱动缺失、URL 方言错误等环境问题也应转成健康状态，而不是让检查接口 500。
        return DatabaseHealth(configured=True, reachable=False, error=exc.__class__.__name__)

    return DatabaseHealth(configured=True, reachable=True)
