from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.paths import CONFIG_SCHEMA_PATH
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:  # pragma: no cover - 运行环境缺依赖时由检查结果承载。
    Draft202012Validator = None  # type: ignore[assignment]


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
            loaded = self.load_active_config(session, active_config_version)
            active_config = loaded[0]
            config_version = loaded[1]
            checks.append(_check_bool(
                "active_config",
                active_config is not None,
                (
                    f"active config v{config_version} loaded"
                    if active_config is not None
                    else "active config is missing or inactive"
                ),
            ))
        else:
            config_version = _json_int(active_config.get("config_version"))
            checks.append(_check_bool(
                "active_config",
                True,
                f"active config payload v{config_version or 'unknown'} loaded",
            ))

        if active_config is None:
            return _result(config_version, schema_revision, checks)

        checks.extend(self._check_active_config_schema(active_config))
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
        row = session.execute(
            text(
                """
                SELECT sc.value_json, sc.version
                FROM system_configs sc
                JOIN config_versions cv ON cv.id = sc.config_version_id
                WHERE sc.key = 'active_config'
                  AND sc.version = :version
                  AND sc.status = 'active'
                  AND cv.status = 'active'
                LIMIT 1
                """
            ),
            {"version": active_config_version},
        ).one_or_none()
        if row is None:
            return None, active_config_version
        value_json = row._mapping["value_json"]
        if isinstance(value_json, dict):
            return value_json, int(row._mapping["version"])
        if isinstance(value_json, str):
            try:
                parsed = json.loads(value_json)
            except json.JSONDecodeError:
                return None, int(row._mapping["version"])
            if isinstance(parsed, dict):
                return parsed, int(row._mapping["version"])
        return None, int(row._mapping["version"])

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
            {"value_json": json.dumps(result.to_state_value(), ensure_ascii=False)},
        )

    def _check_active_config_schema(self, config: dict[str, Any]) -> list[BootstrapCheck]:
        if Draft202012Validator is None:
            return [BootstrapCheck("active_config_schema", "failed", "jsonschema is not installed")]
        started = time.monotonic()
        try:
            schema = json.loads(CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
        except OSError as exc:
            return [
                BootstrapCheck(
                    "active_config_schema",
                    "failed",
                    f"config schema cannot be loaded: {exc.__class__.__name__}",
                )
            ]
        active_schema = {
            "$schema": schema.get("$schema"),
            "$defs": schema.get("$defs", {}),
            "$ref": "#/$defs/ActiveConfigV1",
        }
        errors = sorted(
            Draft202012Validator(active_schema).iter_errors(config),
            key=lambda item: list(item.path),
        )
        if errors:
            first = errors[0]
            path = "$" + "".join(f".{part}" for part in first.path)
            return [
                BootstrapCheck(
                    "active_config_schema",
                    "failed",
                    f"{len(errors)} schema error(s), first at {path}: {first.message}",
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
        redis_config = _as_dict(config.get("redis"))
        redis_url = str(redis_config.get("url") or "")
        pool = _as_dict(redis_config.get("pool"))
        timeout = _timeout_seconds(pool.get("connect_timeout_ms"), default_ms=1000)
        started = time.monotonic()
        try:
            _redis_ping(redis_url, timeout)
        except BootstrapProbeError as exc:
            return BootstrapCheck("redis", "failed", str(exc), latency_ms=_elapsed_ms(started))
        return BootstrapCheck(
            "redis",
            "passed",
            "redis ping succeeded",
            latency_ms=_elapsed_ms(started),
        )

    def _check_minio(self, config: dict[str, Any]) -> BootstrapCheck:
        storage = _as_dict(config.get("storage"))
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
        vector_store = _as_dict(config.get("vector_store"))
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
        keyword_search = _as_dict(config.get("keyword_search"))
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
        gateway = _as_dict(config.get("model_gateway"))
        providers = _as_dict(gateway.get("providers"))
        timeout_ms = _json_int(_as_dict(gateway.get("healthcheck")).get("timeout_ms")) or 2000
        auth_headers: dict[str, str] = {}
        auth_token_ref = gateway.get("auth_token_ref")
        if isinstance(auth_token_ref, str) and auth_token_ref:
            try:
                token = SecretStoreService().get_secret_value(session, secret_ref=auth_token_ref)
            except SecretStoreError as exc:
                return [BootstrapCheck("model_gateway_auth", "failed", str(exc))]
            auth_headers["authorization"] = f"Bearer {token}"

        checks: list[BootstrapCheck] = []
        for provider_name in ("embedding", "rerank", "llm"):
            provider = _as_dict(providers.get(provider_name))
            base_url = str(provider.get("base_url") or "")
            path = str(provider.get("healthcheck_path") or "/health")
            started = time.monotonic()
            try:
                _http_get(
                    _join_url(base_url, path),
                    timeout_seconds=_timeout_seconds(timeout_ms, default_ms=2000),
                    headers=auth_headers,
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


class BootstrapProbeError(Exception):
    """外部依赖探测失败。"""


def _collect_secret_refs(config: dict[str, Any]) -> list[tuple[str, str | None, bool]]:
    storage = _as_dict(config.get("storage"))
    auth = _as_dict(config.get("auth"))
    vector_store = _as_dict(config.get("vector_store"))
    gateway = _as_dict(config.get("model_gateway"))
    return [
        ("secret_minio_access_key", _str_or_none(storage.get("access_key_ref")), True),
        ("secret_minio_secret_key", _str_or_none(storage.get("secret_key_ref")), True),
        ("secret_jwt_signing_key", _str_or_none(auth.get("jwt_signing_key_ref")), True),
        ("secret_qdrant_api_key", _str_or_none(vector_store.get("api_key_ref")), False),
        ("secret_model_gateway_auth", _str_or_none(gateway.get("auth_token_ref")), False),
    ]


def _redis_ping(redis_url: str, timeout: float) -> None:
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
    milliseconds = _json_int(value) or default_ms
    return max(milliseconds / 1000, 0.001)


def _json_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None
