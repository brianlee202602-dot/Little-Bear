"""Index Ops runtime factory。"""

from __future__ import annotations

from app.adapters import QdrantOpsClient
from app.modules.config.errors import ConfigServiceError
from app.modules.config.service import ConfigService
from app.modules.indexing.ops_service import IndexOpsService
from app.modules.secrets.service import SecretStoreError, SecretStoreService
from app.shared.json_utils import as_dict, json_int, json_str
from sqlalchemy.orm import Session


def build_index_ops_service(session: Session) -> IndexOpsService:
    try:
        snapshot = ConfigService().load_active_config(session, validate_schema=False)
    except ConfigServiceError:
        return IndexOpsService(qdrant_config_issue="active_config_unavailable")
    config = snapshot.config
    vector_store = as_dict(config.get("vector_store"))
    timeout_config = as_dict(config.get("timeout"))
    model_config = as_dict(config.get("model"))

    qdrant_base_url = json_str(vector_store, "qdrant_base_url")
    expected_dimension = json_int(model_config, "embedding_dimension")
    if not qdrant_base_url:
        return IndexOpsService(
            expected_dimension=expected_dimension,
            qdrant_config_issue="qdrant_base_url_missing",
        )

    api_key_ref = json_str(vector_store, "api_key_ref")
    try:
        api_key = _secret_value(session, api_key_ref)
    except SecretStoreError:
        return IndexOpsService(
            expected_dimension=expected_dimension,
            qdrant_config_issue="qdrant_api_key_unavailable",
        )

    return IndexOpsService(
        qdrant_inspector=QdrantOpsClient(
            base_url=qdrant_base_url,
            api_key=api_key,
            timeout_seconds=_timeout_seconds(
                json_int(timeout_config, "vector_search_ms"),
                default_ms=3000,
                min_ms=3000,
            ),
        ),
        expected_dimension=expected_dimension,
    )


def _secret_value(session: Session, secret_ref: str | None) -> str | None:
    if not secret_ref:
        return None
    return SecretStoreService().get_secret_value(session, secret_ref=secret_ref)


def _timeout_seconds(timeout_ms: int | None, *, default_ms: int, min_ms: int = 1) -> float:
    return max(timeout_ms or default_ms, min_ms) / 1000
