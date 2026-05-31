"""External dependency probes for service bootstrap."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.setup.bootstrap_types import BootstrapCheck
from app.shared.json_utils import as_dict, json_str
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class BootstrapProbeError(Exception):
    """外部依赖探测失败。"""


class BootstrapProbeService:
    """Probe non-model dependencies used by service bootstrap."""

    def __init__(
        self,
        *,
        redis_ping: Callable[[str, float], None],
        http_get: Callable[..., None],
        join_url: Callable[[str, str], str],
        elapsed_ms: Callable[[float], int],
        timeout_seconds: Callable[..., float],
        secret_store_factory: Callable[[], SecretStoreService] = SecretStoreService,
    ) -> None:
        self._redis_ping = redis_ping
        self._http_get = http_get
        self._join_url = join_url
        self._elapsed_ms = elapsed_ms
        self._timeout_seconds = timeout_seconds
        self._secret_store_factory = secret_store_factory

    def check_secret_refs(
        self,
        session: Session,
        config: dict[str, object],
    ) -> list[BootstrapCheck]:
        refs = _collect_secret_refs(config)
        if not refs:
            return [BootstrapCheck("secret_store", "passed", "no required secret refs")]
        checks: list[BootstrapCheck] = []
        service = self._secret_store_factory()
        for name, secret_ref, required in refs:
            if not secret_ref:
                checks.append(
                    BootstrapCheck(
                        name,
                        "skipped",
                        "secret ref is not configured",
                        required,
                    )
                )
                continue
            started = time.monotonic()
            try:
                service.verify_secret(session, secret_ref=secret_ref)
            except SecretStoreError as exc:
                checks.append(
                    BootstrapCheck(
                        name,
                        "failed",
                        str(exc),
                        required=required,
                        latency_ms=self._elapsed_ms(started),
                    )
                )
            else:
                checks.append(
                    BootstrapCheck(
                        name,
                        "passed",
                        f"{secret_ref} is readable",
                        required=required,
                        latency_ms=self._elapsed_ms(started),
                    )
                )
        return checks

    def check_redis(self, config: dict[str, object]) -> BootstrapCheck:
        redis_config = as_dict(config.get("redis"))
        redis_url = str(redis_config.get("url") or "")
        pool = as_dict(redis_config.get("pool"))
        timeout = self._timeout_seconds(pool.get("connect_timeout_ms"), default_ms=1000)
        started = time.monotonic()
        try:
            self._redis_ping(redis_url, timeout)
        except (BootstrapProbeError, OSError) as exc:
            return BootstrapCheck("redis", "failed", str(exc), latency_ms=self._elapsed_ms(started))
        return BootstrapCheck(
            "redis",
            "passed",
            "redis ping succeeded",
            latency_ms=self._elapsed_ms(started),
        )

    def check_minio(self, config: dict[str, object]) -> BootstrapCheck:
        storage = as_dict(config.get("storage"))
        endpoint = str(storage.get("minio_endpoint") or "")
        started = time.monotonic()
        try:
            self._http_get(
                self._join_url(endpoint, "/minio/health/live"),
                timeout_seconds=2,
            )
        except BootstrapProbeError as exc:
            return BootstrapCheck("minio", "failed", str(exc), latency_ms=self._elapsed_ms(started))
        return BootstrapCheck(
            "minio",
            "passed",
            "minio health check succeeded",
            latency_ms=self._elapsed_ms(started),
        )

    def check_qdrant(self, session: Session, config: dict[str, object]) -> BootstrapCheck:
        vector_store = as_dict(config.get("vector_store"))
        base_url = str(vector_store.get("qdrant_base_url") or "")
        headers: dict[str, str] = {}
        api_key_ref = vector_store.get("api_key_ref")
        if isinstance(api_key_ref, str) and api_key_ref:
            try:
                headers["api-key"] = self._secret_store_factory().get_secret_value(
                    session,
                    secret_ref=api_key_ref,
                )
            except SecretStoreError as exc:
                return BootstrapCheck("qdrant", "failed", str(exc))
        started = time.monotonic()
        try:
            try:
                self._http_get(
                    self._join_url(base_url, "/readyz"),
                    timeout_seconds=2,
                    headers=headers,
                )
            except BootstrapProbeError:
                self._http_get(
                    self._join_url(base_url, "/"),
                    timeout_seconds=2,
                    headers=headers,
                )
        except BootstrapProbeError as exc:
            return BootstrapCheck(
                "qdrant",
                "failed",
                str(exc),
                latency_ms=self._elapsed_ms(started),
            )
        return BootstrapCheck(
            "qdrant",
            "passed",
            "qdrant health check succeeded",
            latency_ms=self._elapsed_ms(started),
        )

    def check_keyword_search(self, session: Session, config: dict[str, object]) -> BootstrapCheck:
        keyword_search = as_dict(config.get("keyword_search"))
        analyzer = str(keyword_search.get("keyword_analyzer") or "little_bear_zh")
        regconfig = "little_bear_zh" if analyzer == "zhparser" else analyzer
        started = time.monotonic()
        try:
            session.execute(
                text("SELECT to_tsvector(CAST(:regconfig AS regconfig), '初始化检查')"),
                {"regconfig": regconfig},
            ).one()
        except SQLAlchemyError as exc:
            return BootstrapCheck(
                "keyword_search",
                "failed",
                f"keyword search check failed: {exc.__class__.__name__}",
                latency_ms=self._elapsed_ms(started),
            )
        return BootstrapCheck(
            "keyword_search",
            "passed",
            f"{regconfig} text search configuration is usable",
            latency_ms=self._elapsed_ms(started),
        )


def _collect_secret_refs(config: dict[str, object]) -> list[tuple[str, str | None, bool]]:
    storage = as_dict(config.get("storage"))
    auth = as_dict(config.get("auth"))
    vector_store = as_dict(config.get("vector_store"))
    gateway = as_dict(config.get("model_gateway"))
    providers = as_dict(gateway.get("providers"))
    refs = [
        ("secret_minio_access_key", json_str(storage.get("access_key_ref")), True),
        ("secret_minio_secret_key", json_str(storage.get("secret_key_ref")), True),
        ("secret_jwt_signing_key", json_str(auth.get("jwt_signing_key_ref")), True),
        ("secret_qdrant_api_key", json_str(vector_store.get("api_key_ref")), False),
        ("secret_model_gateway_auth", json_str(gateway.get("auth_token_ref")), False),
    ]
    for provider_name in ("embedding", "rerank", "llm"):
        provider = as_dict(providers.get(provider_name))
        refs.append(
            (
                f"secret_model_provider_{provider_name}_auth",
                json_str(provider.get("auth_token_ref")),
                False,
            )
        )
    return refs
