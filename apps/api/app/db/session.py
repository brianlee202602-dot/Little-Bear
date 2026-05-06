"""数据库连接和事务上下文。

当前项目把 PostgreSQL 作为事实源。这里集中创建 SQLAlchemy Engine 和 Session，
业务代码通过 session_scope 形成明确的提交/回滚边界。
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.shared.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required")
    # pool_pre_ping 用于在连接池复用前检查连接，降低数据库重启后的坏连接风险。
    return create_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_pool_max_overflow,
        pool_pre_ping=True,
    )


@lru_cache
def create_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session_factory = create_session_factory()
    with session_factory() as session:
        yield session


@contextmanager
def session_scope() -> Iterator[Session]:
    """提供同步事务边界：正常退出提交，异常退出回滚。"""

    session_factory = create_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    create_session_factory.cache_clear()
