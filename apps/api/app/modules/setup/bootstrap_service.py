"""ServiceBootstrap 依赖检查。

初始化提交和已初始化进程启动都会走这里，确认 active_config 指向的 Redis、Secret、
MinIO、Qdrant、关键词检索和外部模型 provider 至少可连通。它不替代各业务模块的
运行期重试/降级，只提供 ready 门禁。
"""

from __future__ import annotations

import ast
import socket
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.config.validator import ConfigSchemaValidator
from app.modules.secrets.service import SecretStoreService
from app.modules.setup.bootstrap_probe_service import BootstrapProbeError, BootstrapProbeService
from app.modules.setup.bootstrap_state_repository import ServiceBootstrapStateRepository
from app.modules.setup.bootstrap_types import (
    BootstrapCheck,
    ServiceBootstrapResult,
    ServiceBootstrapState,
)
from app.modules.setup.provider_probe_service import ProviderProbeService
from app.shared.json_utils import json_int
from sqlalchemy.orm import Session


def _expected_schema_revision() -> str:
    versions_dir = Path(__file__).resolve().parents[3] / "migrations" / "versions"
    revisions: list[tuple[str, str]] = []
    for path in versions_dir.glob("*.py"):
        if path.name.startswith("__"):
            continue
        revision = _revision_from_file(path)
        if revision:
            revisions.append((path.name, revision))
    if not revisions:
        return "0005_jobs_audit_cache"
    return sorted(revisions, key=lambda item: item[0])[-1][1]


def _revision_from_file(path: Path) -> str | None:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        is_revision_assignment = any(
            isinstance(target, ast.Name) and target.id == "revision" for target in node.targets
        )
        if not is_revision_assignment:
            continue
        value = ast.literal_eval(node.value)
        return value if isinstance(value, str) and value else None
    return None


EXPECTED_SCHEMA_REVISION = _expected_schema_revision()


class ServiceBootstrapService:
    """校验 active_config 驱动的关键服务是否可用。"""

    def __init__(
        self,
        *,
        state_repository: ServiceBootstrapStateRepository | None = None,
        probe_service: BootstrapProbeService | None = None,
        provider_probe_service: ProviderProbeService | None = None,
        config_service: ConfigService | None = None,
        schema_validator: ConfigSchemaValidator | None = None,
    ) -> None:
        self.state_repository = state_repository or ServiceBootstrapStateRepository()
        self.probe_service = probe_service or BootstrapProbeService(
            redis_ping=_redis_ping,
            http_get=_http_get,
            join_url=_join_url,
            elapsed_ms=_elapsed_ms,
            timeout_seconds=_timeout_seconds,
            secret_store_factory=SecretStoreService,
        )
        self.provider_probe_service = provider_probe_service or ProviderProbeService(
            http_get=_http_get,
            join_url=_join_url,
            elapsed_ms=_elapsed_ms,
            timeout_seconds=_timeout_seconds,
            secret_store_factory=SecretStoreService,
        )
        self.config_service = config_service or ConfigService()
        self.schema_validator = schema_validator or ConfigSchemaValidator()

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
                snapshot = self.config_service.load_active_config(
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
        return self.state_repository.load_schema_revision(session)

    def load_active_config(
        self, session: Session, active_config_version: int | None
    ) -> tuple[dict[str, Any] | None, int | None]:
        if active_config_version is None:
            return None, None
        try:
            snapshot = self.config_service.load_active_config(
                session,
                active_config_version=active_config_version,
                validate_schema=False,
            )
        except ConfigServiceError:
            return None, active_config_version
        return snapshot.config, snapshot.version

    def persist_result(self, session: Session, result: ServiceBootstrapResult) -> None:
        self.state_repository.persist_result(session, result)

    def _check_active_config_schema(self, config: dict[str, Any]) -> list[BootstrapCheck]:
        started = time.monotonic()
        try:
            issues = self.schema_validator.validate_active_config(config)
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
        return self.probe_service.check_secret_refs(session, config)

    def _check_redis(self, config: dict[str, Any]) -> BootstrapCheck:
        return self.probe_service.check_redis(config)

    def _check_minio(self, config: dict[str, Any]) -> BootstrapCheck:
        return self.probe_service.check_minio(config)

    def _check_qdrant(self, session: Session, config: dict[str, Any]) -> BootstrapCheck:
        return self.probe_service.check_qdrant(session, config)

    def _check_keyword_search(self, session: Session, config: dict[str, Any]) -> BootstrapCheck:
        return self.probe_service.check_keyword_search(session, config)

    def _check_model_providers(
        self,
        session: Session,
        config: dict[str, Any],
    ) -> list[BootstrapCheck]:
        return self.provider_probe_service.check_model_providers(session, config)


class ServiceBootstrapStateService:
    """读取和刷新 service_bootstrap 状态，避免每个入口重复执行外部依赖探测。"""

    def __init__(
        self,
        *,
        bootstrap_service: ServiceBootstrapService | None = None,
        state_repository: ServiceBootstrapStateRepository | None = None,
        ttl_seconds: float = 30.0,
    ) -> None:
        self.bootstrap_service = bootstrap_service or ServiceBootstrapService()
        self.state_repository = state_repository or ServiceBootstrapStateRepository()
        self.ttl_seconds = ttl_seconds

    def load_state(self, session: Session) -> ServiceBootstrapState | None:
        return self.state_repository.load_state(session)

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


def _timeout_seconds(value: object, *, default_ms: int) -> float:
    milliseconds = json_int(value) or default_ms
    return max(milliseconds / 1000, 0.001)
