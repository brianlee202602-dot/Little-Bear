from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """进程设置。

    启动层只保留数据库连接和运行参数。
    业务配置必须在初始化完成后通过 ConfigService 从 active_config 加载。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="local", alias="APP_ENV")
    service_name: str = Field(default="api", alias="SERVICE_NAME")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    admin_setup_url: str = Field(
        default="http://localhost:5174/admin/setup-initialization",
        alias="ADMIN_SETUP_URL",
    )
    setup_token_log_enabled: bool = Field(default=True, alias="SETUP_TOKEN_LOG_ENABLED")
    setup_token_signing_secret: str | None = Field(default=None, alias="SETUP_TOKEN_SIGNING_SECRET")
    secret_store_master_key: str | None = Field(default=None, alias="SECRET_STORE_MASTER_KEY")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    database_connect_timeout_seconds: int = Field(
        default=5, alias="DATABASE_CONNECT_TIMEOUT_SECONDS"
    )
    database_pool_size: int = Field(default=5, alias="DATABASE_POOL_SIZE")
    database_pool_max_overflow: int = Field(default=10, alias="DATABASE_POOL_MAX_OVERFLOW")
    database_ssl_mode: str | None = Field(default=None, alias="DATABASE_SSL_MODE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
