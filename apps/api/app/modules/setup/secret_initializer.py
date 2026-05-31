"""Provider secret preparation during setup initialization."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from app.modules.setup.contracts import (
    MODEL_PROVIDER_SECRET_FIELDS,
    SetupInitializationError,
)
from app.shared.json_utils import as_dict
from sqlalchemy.orm import Session


class ModelProviderSecretInitializer:
    """Write plaintext provider tokens to Secret Store and rewrite config refs."""

    def __init__(
        self,
        *,
        secret_store_factory: Callable[[], Any],
        secret_error_type: type[Exception],
    ) -> None:
        self._secret_store_factory = secret_store_factory
        self._secret_error_type = secret_error_type

    def prepare(self, session: Session, payload: dict[str, Any]) -> dict[str, Any]:
        prepared_payload = deepcopy(payload)
        setup = as_dict(prepared_payload.get("setup"))
        config = as_dict(prepared_payload.get("config"))
        model_provider_secrets = as_dict(setup.pop("model_provider_secrets", None))
        model_gateway = as_dict(config.get("model_gateway"))
        providers = as_dict(model_gateway.get("providers"))

        for provider_name, (secret_field, secret_ref) in MODEL_PROVIDER_SECRET_FIELDS.items():
            secret_value = model_provider_secrets.get(secret_field)
            if not isinstance(secret_value, str) or not secret_value.strip():
                continue

            provider = as_dict(providers.get(provider_name))
            try:
                self._secret_store_factory().put_secret(
                    session,
                    secret_ref=secret_ref,
                    secret_value=secret_value.strip(),
                )
            except self._secret_error_type as exc:
                raise SetupInitializationError(
                    "SETUP_SECRET_WRITE_FAILED",
                    f"failed to store model provider secret for {provider_name}",
                    status_code=500,
                    details={
                        "provider": provider_name,
                        "secret_ref": secret_ref,
                        "reason": str(exc),
                    },
                ) from exc
            provider["auth_token_ref"] = secret_ref
            providers[provider_name] = provider

        model_gateway["providers"] = providers
        config["model_gateway"] = model_gateway
        prepared_payload["setup"] = setup
        prepared_payload["config"] = config
        return prepared_payload
