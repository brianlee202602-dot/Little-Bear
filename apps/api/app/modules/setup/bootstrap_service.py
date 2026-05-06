"""ServiceBootstrap 依赖检查。

初始化提交和已初始化进程启动都会走这里，确认 active_config 指向的 Redis、Secret、
MinIO、Qdrant、关键词检索和外部模型 provider 至少可连通。它不替代各业务模块的
运行期重试/降级，只提供 ready 门禁。
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.config.validator import ConfigSchemaValidator
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_bool, json_dumps, json_int, json_str
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

EXPECTED_SCHEMA_REVISION = "0005_jobs_audit_cache"
CheckStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class BootstrapCheck:
    name: str
    status: CheckStatus
    message: str
    required: bool = True
    latency_ms: int | None = None

    @property
    def passed(self) -> bool:
        return self.status == "passed" or (self.status == "skipped" and not self.required)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "required": self.required,
        }
        if self.latency_ms is not None:
            data["latency_ms"] = self.latency_ms
        return data


@dataclass(frozen=True)
class ServiceBootstrapResult:
    ready: bool
    config_version: int | None
    schema_revision: str | None
    checks: tuple[BootstrapCheck, ...]

    def to_state_value(self) -> dict[str, object]:
        return {
            "ready": self.ready,
            "mode": "p0_dependency_checks",
            "targets": [check.name for check in self.checks],
            "config_version": self.config_version,
            "schema_migration_version": self.schema_revision,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class ServiceBootstrapState:
    ready: bool
    config_version: int | None
    schema_revision: str | None
    checks: tuple[BootstrapCheck, ...]
    updated_at: datetime | None

    def fresh_for(self, active_config_version: int | None, *, ttl_seconds: float) -> bool:
        if not self.ready or self.config_version != active_config_version:
            return False
        if self.updated_at is None:
            return False
        return datetime.now(UTC) - self.updated_at <= timedelta(seconds=max(ttl_seconds, 0.0))

    def to_result(self) -> ServiceBootstrapResult:
        return ServiceBootstrapResult(
            ready=self.ready,
            config_version=self.config_version,
            schema_revision=self.schema_revision,
            checks=self.checks,
        )


class ServiceBootstrapService:
    """校验 active_config 驱动的关键服务是否可用。"""

    def bootstrap(
        self,
        session: Session,
        *,
        active_config_version: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> ServiceBootstrapResult:
        checks: list[BootstrapCheck] = []
        # migration 是所有业务表和扩展的底座，优先检查，便于排障。
        schema_revision = self.load_schema_revision(session)
        checks.append(_check_bool(
            "migration",
            schema_revision == EXPECTED_SCHEMA_REVISION,
            (
                f"schema revision is {schema_revision}"
                if schema_revision
                else "schema revision is missing"
            ),
        ))

        config_version: int | None = None
        active_config = config
        if active_config is None:
            started = time.monotonic()
            try:
                snapshot = ConfigService().load_active_config(
                    session,
                    active_config_version=active_config_version,
                    validate_schema=False,
                )
            except ConfigServiceError as exc:
                config_version = active_config_version
                checks.append(
                    BootstrapCheck(
                        "active_config",
                        "failed",
                        f"{exc.error_code}: {exc.message}",
                        latency_ms=_elapsed_ms(started),
                    )
                )
            else:
                active_config = snapshot.config
                config_version = snapshot.version
                checks.append(
                    BootstrapCheck(
                        "active_config",
                        "passed",
                        f"active config v{config_version} loaded",
                        latency_ms=_elapsed_ms(started),
                    )
                )
        else:
            config_version = json_int(active_config.get("config_version"))
            checks.append(_check_bool(
                "active_config",
                True,
                f"active config payload v{config_version or 'unknown'} loaded",
            ))

        if active_config is None:
            return _result(config_version, schema_revision, checks)

        checks.extend(self._check_active_config_schema(active_config))
        # Secret 只验证 ref 可读，不把明文放进检查结果。
        checks.extend(self._check_secret_refs(session, active_config))
        checks.append(self._check_redis(active_config))
        checks.append(self._check_minio(active_config))
        checks.append(self._check_qdrant(session, active_config))
        checks.append(self._check_keyword_search(session, active_config))
        checks.extend(self._check_model_providers(session, active_config))
        return _result(config_version, schema_revision, checks)

    def load_schema_revision(self, session: Session) -> str | None:
        try:
            row = session.execute(
                text("SELECT version_num FROM alembic_version LIMIT 1")
            ).one_or_none()
        except SQLAlchemyError:
            return None
        if row is None:
            return None
        value = row._mapping["version_num"]
        return value if isinstance(value, str) and value else None

    def load_active_config(
        self, session: Session, active_config_version: int | None
    ) -> tuple[dict[str, Any] | None, int | None]:
        if active_config_version is None:
            return None, None
        try:
            snapshot = ConfigService().load_active_config(
                session,
                active_config_version=active_config_version,
                validate_schema=False,
            )
        except ConfigServiceError:
            return None, active_config_version
        return snapshot.config, snapshot.version

    def persist_result(self, session: Session, result: ServiceBootstrapResult) -> None:
        session.execute(
            text(
                """
                INSERT INTO system_state(key, value_json)
                VALUES ('service_bootstrap', CAST(:value_json AS jsonb))
                ON CONFLICT (key) DO UPDATE
                SET value_json = EXCLUDED.value_json, updated_at = now()
                """
            ),
            {"value_json": json_dumps(result.to_state_value())},
        )

    def _check_active_config_schema(self, config: dict[str, Any]) -> list[BootstrapCheck]:
        started = time.monotonic()
        try:
            issues = ConfigSchemaValidator().validate_active_config(config)
        except ConfigServiceError as exc:
            return [
                BootstrapCheck(
                    "active_config_schema",
                    "failed",
                    f"{exc.error_code}: {exc.message}",
                    latency_ms=_elapsed_ms(started),
                )
            ]
        if issues:
            first = issues[0]
            return [
                BootstrapCheck(
                    "active_config_schema",
                    "failed",
                    f"{len(issues)} schema error(s), first at {first.path}: {first.message}",
                    latency_ms=_elapsed_ms(started),
                )
            ]
        return [
            BootstrapCheck(
                "active_config_schema",
                "passed",
                "active config schema is valid",
                latency_ms=_elapsed_ms(started),
            )
        ]

    def _check_secret_refs(self, session: Session, config: dict[str, Any]) -> list[BootstrapCheck]:
        refs = _collect_secret_refs(config)
        if not refs:
            return [BootstrapCheck("secret_store", "passed", "no required secret refs")]
        checks: list[BootstrapCheck] = []
        service = SecretStoreService()
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
                        latency_ms=_elapsed_ms(started),
                    )
                )
            else:
                checks.append(
                    BootstrapCheck(
                        name,
                        "passed",
                        f"{secret_ref} is readable",
                        required=required,
                        latency_ms=_elapsed_ms(started),
                    )
                )
        return checks

    def _check_redis(self, config: dict[str, Any]) -> BootstrapCheck:
        redis_config = as_dict(config.get("redis"))
        redis_url = str(redis_config.get("url") or "")
        pool = as_dict(redis_config.get("pool"))
        timeout = _timeout_seconds(pool.get("connect_timeout_ms"), default_ms=1000)
        started = time.monotonic()
        try:
            _redis_ping(redis_url, timeout)
        except (BootstrapProbeError, OSError) as exc:
            return BootstrapCheck("redis", "failed", str(exc), latency_ms=_elapsed_ms(started))
        return BootstrapCheck(
            "redis",
            "passed",
            "redis ping succeeded",
            latency_ms=_elapsed_ms(started),
        )

    def _check_minio(self, config: dict[str, Any]) -> BootstrapCheck:
        storage = as_dict(config.get("storage"))
        endpoint = str(storage.get("minio_endpoint") or "")
        started = time.monotonic()
        try:
            _http_get(_join_url(endpoint, "/minio/health/live"), timeout_seconds=2)
        except BootstrapProbeError as exc:
            return BootstrapCheck("minio", "failed", str(exc), latency_ms=_elapsed_ms(started))
        return BootstrapCheck(
            "minio",
            "passed",
            "minio health check succeeded",
            latency_ms=_elapsed_ms(started),
        )

    def _check_qdrant(self, session: Session, config: dict[str, Any]) -> BootstrapCheck:
        vector_store = as_dict(config.get("vector_store"))
        base_url = str(vector_store.get("qdrant_base_url") or "")
        headers: dict[str, str] = {}
        api_key_ref = vector_store.get("api_key_ref")
        if isinstance(api_key_ref, str) and api_key_ref:
            try:
                headers["api-key"] = SecretStoreService().get_secret_value(
                    session,
                    secret_ref=api_key_ref,
                )
            except SecretStoreError as exc:
                return BootstrapCheck("qdrant", "failed", str(exc))
        started = time.monotonic()
        try:
            try:
                _http_get(_join_url(base_url, "/readyz"), timeout_seconds=2, headers=headers)
            except BootstrapProbeError:
                _http_get(_join_url(base_url, "/"), timeout_seconds=2, headers=headers)
        except BootstrapProbeError as exc:
            return BootstrapCheck("qdrant", "failed", str(exc), latency_ms=_elapsed_ms(started))
        return BootstrapCheck(
            "qdrant",
            "passed",
            "qdrant health check succeeded",
            latency_ms=_elapsed_ms(started),
        )

    def _check_keyword_search(self, session: Session, config: dict[str, Any]) -> BootstrapCheck:
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
                latency_ms=_elapsed_ms(started),
            )
        return BootstrapCheck(
            "keyword_search",
            "passed",
            f"{regconfig} text search configuration is usable",
            latency_ms=_elapsed_ms(started),
        )

    def _check_model_providers(
        self,
        session: Session,
        config: dict[str, Any],
    ) -> list[BootstrapCheck]:
        gateway = as_dict(config.get("model_gateway"))
        providers = as_dict(gateway.get("providers"))
        timeout_ms = json_int(as_dict(gateway.get("healthcheck")).get("timeout_ms")) or 2000
        gateway_auth_token_ref = json_str(gateway.get("auth_token_ref"))

        checks: list[BootstrapCheck] = []
        for provider_name in ("embedding", "rerank", "llm"):
            # provider 允许单独配置 auth_token_ref；没有时回退 model_gateway.auth_token_ref。
            provider = as_dict(providers.get(provider_name))
            base_url = str(provider.get("base_url") or "")
            path = str(provider.get("healthcheck_path") or "/health")
            auth_headers_result = _model_provider_auth_headers(
                session,
                provider_name,
                json_str(provider.get("auth_token_ref")) or gateway_auth_token_ref,
            )
            if isinstance(auth_headers_result, BootstrapCheck):
                checks.append(auth_headers_result)
                continue
            started = time.monotonic()
            try:
                _http_get(
                    _join_url(base_url, path),
                    timeout_seconds=_timeout_seconds(timeout_ms, default_ms=2000),
                    headers=auth_headers_result,
                )
            except BootstrapProbeError as exc:
                checks.append(
                    BootstrapCheck(
                        f"model_provider_{provider_name}",
                        "failed",
                        str(exc),
                        latency_ms=_elapsed_ms(started),
                    )
                )
            else:
                checks.append(
                    BootstrapCheck(
                        f"model_provider_{provider_name}",
                        "passed",
                        f"{provider_name} provider health check succeeded",
                        latency_ms=_elapsed_ms(started),
                    )
                )
        return checks


class ServiceBootstrapStateService:
    """读取和刷新 service_bootstrap 状态，避免每个入口重复执行外部依赖探测。"""

    def __init__(
        self,
        *,
        bootstrap_service: ServiceBootstrapService | None = None,
        ttl_seconds: float = 30.0,
    ) -> None:
        self.bootstrap_service = bootstrap_service or ServiceBootstrapService()
        self.ttl_seconds = ttl_seconds

    def load_state(self, session: Session) -> ServiceBootstrapState | None:
        try:
            row = session.execute(
                text(
                    """
                    SELECT value_json, updated_at
                    FROM system_state
                    WHERE key = 'service_bootstrap'
                    LIMIT 1
                    """
                )
            ).one_or_none()
        except SQLAlchemyError:
            return None
        if row is None:
            return None
        value_json = as_dict(row._mapping["value_json"])
        return ServiceBootstrapState(
            ready=json_bool(value_json, "ready", default=False),
            config_version=json_int(value_json, "config_version"),
            schema_revision=json_str(value_json, "schema_migration_version"),
            checks=_checks_from_state(value_json.get("checks")),
            updated_at=_datetime_or_none(row._mapping.get("updated_at")),
        )

    def ensure_ready(
        self,
        session: Session,
        *,
        active_config_version: int | None,
        force_refresh: bool = False,
    ) -> ServiceBootstrapResult:
        if active_config_version is None:
            return ServiceBootstrapResult(
                ready=False,
                config_version=None,
                schema_revision=self.bootstrap_service.load_schema_revision(session),
                checks=(
                    BootstrapCheck(
                        "active_config",
                        "failed",
                        "system_state.active_config_version is missing",
                    ),
                ),
            )

        state = None if force_refresh else self.load_state(session)
        if state and state.fresh_for(active_config_version, ttl_seconds=self.ttl_seconds):
            return state.to_result()

        result = self.bootstrap_service.bootstrap(
            session,
            active_config_version=active_config_version,
        )
        self.bootstrap_service.persist_result(session, result)
        return result


class BootstrapProbeError(Exception):
    """外部依赖探测失败。"""


def _collect_secret_refs(config: dict[str, Any]) -> list[tuple[str, str | None, bool]]:
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


def _checks_from_state(value: object) -> tuple[BootstrapCheck, ...]:
    if not isinstance(value, list):
        return ()
    checks: list[BootstrapCheck] = []
    for item in value:
        data = as_dict(item)
        raw_status = data.get("status")
        status: CheckStatus = "failed"
        if raw_status == "passed":
            status = "passed"
        elif raw_status == "skipped":
            status = "skipped"
        checks.append(
            BootstrapCheck(
                name=json_str(data.get("name"), default="unknown") or "unknown",
                status=status,
                message=json_str(data.get("message"), default="") or "",
                required=data.get("required") is not False,
                latency_ms=json_int(data.get("latency_ms")),
            )
        )
    return tuple(checks)


def _model_provider_auth_headers(
    session: Session,
    provider_name: str,
    auth_token_ref: str | None,
) -> dict[str, str] | BootstrapCheck:
    if not auth_token_ref:
        return {}
    try:
        token = SecretStoreService().get_secret_value(session, secret_ref=auth_token_ref)
    except SecretStoreError as exc:
        return BootstrapCheck(f"model_provider_{provider_name}_auth", "failed", str(exc))
    return {"authorization": f"Bearer {token}"}


def _redis_ping(redis_url: str, timeout: float) -> None:
    """不用引入 redis 客户端，仅按 RESP 协议发送 PING 做最小依赖检查。"""

    parsed = urlparse(redis_url)
    if parsed.scheme != "redis" or not parsed.hostname:
        raise BootstrapProbeError("redis url is invalid")
    port = parsed.port or 6379
    password = parsed.password
    with socket.create_connection((parsed.hostname, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        if password:
            _redis_command(sock, "AUTH", password)
        response = _redis_command(sock, "PING")
    if not response.startswith(b"+PONG"):
        raise BootstrapProbeError("redis ping returned unexpected response")


def _redis_command(sock: socket.socket, *parts: str) -> bytes:
    payload = f"*{len(parts)}\r\n".encode("ascii")
    for part in parts:
        data = part.encode("utf-8")
        payload += f"${len(data)}\r\n".encode("ascii") + data + b"\r\n"
    sock.sendall(payload)
    response = sock.recv(128)
    if response.startswith(b"-"):
        raise BootstrapProbeError(response.decode("utf-8", errors="replace").strip())
    return response


def _http_get(
    url: str,
    *,
    timeout_seconds: float,
    headers: dict[str, str] | None = None,
) -> None:
    if not url.startswith(("http://", "https://")):
        raise BootstrapProbeError("http url is invalid")
    request = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            response.read(1)
    except HTTPError as exc:
        raise BootstrapProbeError(f"GET {url} failed with HTTP {exc.code}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise BootstrapProbeError(f"GET {url} failed: {exc.__class__.__name__}") from exc
    if status < 200 or status >= 400:
        raise BootstrapProbeError(f"GET {url} returned HTTP {status}")


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _check_bool(
    name: str,
    condition: bool,
    message: str,
    *,
    required: bool = True,
) -> BootstrapCheck:
    return BootstrapCheck(name, "passed" if condition else "failed", message, required=required)


def _result(
    config_version: int | None,
    schema_revision: str | None,
    checks: list[BootstrapCheck],
) -> ServiceBootstrapResult:
    ready = all(check.passed for check in checks)
    return ServiceBootstrapResult(
        ready=ready,
        config_version=config_version,
        schema_revision=schema_revision,
        checks=tuple(checks),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _datetime_or_none(value: Any) -> datetime | None:
    return value if isinstance(value, datetime) else None


def _timeout_seconds(value: object, *, default_ms: int) -> float:
    milliseconds = json_int(value) or default_ms
    return max(milliseconds / 1000, 0.001)
