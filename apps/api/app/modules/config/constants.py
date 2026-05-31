"""Config module constants."""

from __future__ import annotations

from app.modules.config.cache import ConfigCache

GLOBAL_CONFIG_CACHE = ConfigCache()

CONFIG_METADATA_KEYS = {"schema_version", "config_version", "scope"}

HIGH_RISK_CONFIG_KEYS = {
    "auth",
    "audit",
    "model",
    "model_gateway",
    "permission",
    "retrieval",
    "secret_provider",
    "security",
    "storage",
    "vector_store",
}

MEDIUM_RISK_CONFIG_KEYS = {
    "cache",
    "chunking",
    "import",
    "keyword_search",
    "llm",
    "degrade",
    "observability",
    "rate_limit",
    "redis",
    "timeout",
}
