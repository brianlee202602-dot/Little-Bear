"""Setup 初始化共享契约与内置角色定义。"""

from __future__ import annotations

from dataclasses import dataclass

BUILTIN_ROLE_NAMES = {
    "system_admin",
    "security_admin",
    "audit_admin",
    "department_admin",
    "knowledge_base_admin",
    "employee",
}

MODEL_PROVIDER_SECRET_FIELDS = {
    "embedding": ("embedding_auth_token", "secret://rag/model/embedding-api-key"),
    "rerank": ("rerank_auth_token", "secret://rag/model/rerank-api-key"),
    "llm": ("llm_auth_token", "secret://rag/model/llm-api-key"),
}


class SetupInitializationError(Exception):
    """初始化执行失败，带结构化错误码。"""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


@dataclass(frozen=True)
class SetupValidationResult:
    valid: bool
    errors: list[dict[str, object]]
    warnings: list[dict[str, object]]


@dataclass(frozen=True)
class SetupInitializationResult:
    initialized: bool
    active_config_version: int
    enterprise_id: str
    admin_user_id: str


def issue(
    error_code: str,
    path: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, object]:
    return {
        "error_code": error_code,
        "path": path,
        "message": message,
        "retryable": retryable,
    }


def setup_schema_error_code(config_error_code: str) -> str:
    if config_error_code == "CONFIG_SCHEMA_VALIDATOR_UNAVAILABLE":
        return "SETUP_DEPENDENCY_MISSING"
    if config_error_code == "CONFIG_SCHEMA_UNAVAILABLE":
        return "SETUP_SCHEMA_UNAVAILABLE"
    if config_error_code == "CONFIG_SCHEMA_MALFORMED":
        return "SETUP_SCHEMA_MALFORMED"
    return "SETUP_CONFIG_INVALID"


def role_scope_type(role_code: str) -> str:
    if role_code == "department_admin":
        return "department"
    if role_code == "knowledge_base_admin":
        return "knowledge_base"
    return "enterprise"


def role_scopes(role_code: str) -> list[str]:
    scopes_by_role = {
        "system_admin": ["*"],
        "security_admin": ["security:*", "permission:*"],
        "audit_admin": ["audit:read", "query_log:read", "model_call:read"],
        "department_admin": [
            "department:*",
            "user:read",
            "user:manage",
            "knowledge_base:read",
            "document:read",
            "rag:query",
        ],
        "knowledge_base_admin": [
            "knowledge_base:*",
            "folder:*",
            "document:*",
            "document:import",
            "import_job:read:self",
            "import_job:manage:self",
            "import_job:read",
            "import:*",
        ],
        "employee": ["knowledge_base:read", "rag:query", "document:read"],
    }
    return scopes_by_role.get(role_code, [])

