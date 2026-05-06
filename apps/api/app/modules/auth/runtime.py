"""Auth 运行时配置缓存。

Auth 请求需要同时读取 active_config.auth 和 Secret Store 中的 JWT signing key。这里按
active_config 版本和 signing key ref 做进程内缓存，避免每次鉴权都重复解密密钥。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.modules.config.service import ConfigService
from app.modules.secrets.service import SecretStoreService
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class AuthRuntimeConfig:
    config_version: int
    auth_config: dict[str, Any] = field(repr=False)
    jwt_issuer: str
    jwt_audience: str
    jwt_signing_key_ref: str
    jwt_signing_secret: str = field(repr=False)


class AuthRuntimeConfigProvider:
    """加载并缓存 Auth 运行时配置和 JWT signing key。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cached: AuthRuntimeConfig | None = None

    def get(
        self,
        session: Session,
        *,
        config_service: ConfigService,
        secret_store: SecretStoreService,
    ) -> AuthRuntimeConfig:
        # 优先走 ConfigService 进程缓存；缓存过期时再由 ConfigService 校验数据库。
        snapshot = config_service.get_active_config()
        auth_config = snapshot.section("auth")
        signing_key_ref = auth_config.get("jwt_signing_key_ref")
        if not isinstance(signing_key_ref, str) or not signing_key_ref:
            raise RuntimeError("auth.jwt_signing_key_ref is missing")

        with self._lock:
            if (
                self._cached is not None
                and self._cached.config_version == snapshot.version
                and self._cached.jwt_signing_key_ref == signing_key_ref
            ):
                return self._cached

            signing_secret = secret_store.get_secret_value(session, secret_ref=signing_key_ref)
            runtime = AuthRuntimeConfig(
                config_version=snapshot.version,
                auth_config=auth_config,
                jwt_issuer=str(auth_config["jwt_issuer"]),
                jwt_audience=str(auth_config["jwt_audience"]),
                jwt_signing_key_ref=signing_key_ref,
                jwt_signing_secret=signing_secret,
            )
            self._cached = runtime
            return runtime

    def invalidate(self) -> None:
        with self._lock:
            self._cached = None


GLOBAL_AUTH_RUNTIME_CONFIG_PROVIDER = AuthRuntimeConfigProvider()
