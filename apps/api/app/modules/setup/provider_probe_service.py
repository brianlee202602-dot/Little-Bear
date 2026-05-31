"""Model provider probes for service bootstrap."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.modules.setup.bootstrap_probe_service import BootstrapProbeError
from app.modules.setup.bootstrap_types import BootstrapCheck
from app.shared.json_utils import as_dict, json_int, json_str
from sqlalchemy.orm import Session


class ProviderProbeService:
    """Probe model provider health endpoints."""

    def __init__(
        self,
        *,
        http_get: Callable[..., None],
        join_url: Callable[[str, str], str],
        elapsed_ms: Callable[[float], int],
        timeout_seconds: Callable[..., float],
        secret_store_factory: Callable[[], SecretStoreService] = SecretStoreService,
    ) -> None:
        self._http_get = http_get
        self._join_url = join_url
        self._elapsed_ms = elapsed_ms
        self._timeout_seconds = timeout_seconds
        self._secret_store_factory = secret_store_factory

    def check_model_providers(
        self,
        session: Session,
        config: dict[str, object],
    ) -> list[BootstrapCheck]:
        gateway = as_dict(config.get("model_gateway"))
        providers = as_dict(gateway.get("providers"))
        timeout_ms = json_int(as_dict(gateway.get("healthcheck")).get("timeout_ms")) or 2000
        gateway_auth_token_ref = json_str(gateway.get("auth_token_ref"))

        checks: list[BootstrapCheck] = []
        for provider_name in ("embedding", "rerank", "llm"):
            provider = as_dict(providers.get(provider_name))
            base_url = str(provider.get("base_url") or "")
            path = str(provider.get("healthcheck_path") or "/health")
            auth_headers_result = self._model_provider_auth_headers(
                session,
                provider_name,
                json_str(provider.get("auth_token_ref")) or gateway_auth_token_ref,
            )
            if isinstance(auth_headers_result, BootstrapCheck):
                checks.append(auth_headers_result)
                continue
            started = time.monotonic()
            try:
                self._http_get(
                    self._join_url(base_url, path),
                    timeout_seconds=self._timeout_seconds(timeout_ms, default_ms=2000),
                    headers=auth_headers_result,
                )
            except BootstrapProbeError as exc:
                checks.append(
                    BootstrapCheck(
                        f"model_provider_{provider_name}",
                        "failed",
                        str(exc),
                        latency_ms=self._elapsed_ms(started),
                    )
                )
            else:
                checks.append(
                    BootstrapCheck(
                        f"model_provider_{provider_name}",
                        "passed",
                        f"{provider_name} provider health check succeeded",
                        latency_ms=self._elapsed_ms(started),
                    )
                )
        return checks

    def _model_provider_auth_headers(
        self,
        session: Session,
        provider_name: str,
        auth_token_ref: str | None,
    ) -> dict[str, str] | BootstrapCheck:
        if not auth_token_ref:
            return {}
        try:
            token = self._secret_store_factory().get_secret_value(
                session,
                secret_ref=auth_token_ref,
            )
        except SecretStoreError as exc:
            return BootstrapCheck(f"model_provider_{provider_name}_auth", "failed", str(exc))
        return {"authorization": f"Bearer {token}"}
