from __future__ import annotations

from pathlib import Path

import yaml
from app.main import create_app

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
CONTRACT_PATH = Path("docs/contracts/openapi.yaml")

# OpenAPI 中保留但后端未挂载的契约操作。实现对应接口时应同步删除保留标记，
# 让契约测试继续约束 OpenAPI 与实际路由的一致性。
EXPECTED_CONTRACT_ONLY_OPERATIONS = {
    ("/internal/v1/admin/roles", "POST"),
    ("/internal/v1/admin/roles/{role_id}", "DELETE"),
    ("/internal/v1/admin/roles/{role_id}", "PATCH"),
    ("/internal/v1/model-catalog", "GET"),
    ("/internal/v1/model-chat-completions", "POST"),
    ("/internal/v1/model-embeddings", "POST"),
    ("/internal/v1/model-health", "GET"),
    ("/internal/v1/model-rerankings", "POST"),
    ("/internal/v1/permission-evaluations", "GET"),
}


def test_all_implemented_routes_are_declared_in_openapi_contract() -> None:
    undocumented = _actual_operations() - _contract_operations()

    assert undocumented == set()


def test_contract_only_operations_match_tracked_gap() -> None:
    contract_only = _contract_operations() - _actual_operations()

    assert contract_only == EXPECTED_CONTRACT_ONLY_OPERATIONS


def test_contract_only_operations_are_marked_as_reserved() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    paths = contract.get("paths") or {}
    missing_stage: set[tuple[str, str]] = set()
    for path, method in EXPECTED_CONTRACT_ONLY_OPERATIONS:
        operation = (paths.get(path) or {}).get(method.lower()) or {}
        if operation.get("x-contract-status") != "reserved":
            missing_stage.add((path, method))

    assert missing_stage == set()


def test_setup_state_contract_uses_current_setup_jwt_fields() -> None:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    schema = contract["components"]["schemas"]["SetupStateResponse"]["properties"]["data"]
    properties = schema["properties"]

    assert {"setup_required", "active_config_present", "setup_token_expires_at"} <= set(
        properties
    )
    assert "system_token_expires_at" not in properties
    assert {"initialized", "setup_status", "setup_required", "active_config_present"} <= set(
        schema["required"]
    )


def _actual_operations() -> set[tuple[str, str]]:
    app = create_app(run_startup_checks=False)
    operations: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        if not path or path.startswith(("/docs", "/redoc", "/openapi")):
            continue
        for method in getattr(route, "methods", set()) or set():
            if method in HTTP_METHODS:
                operations.add((path, method))
    return operations


def _contract_operations() -> set[tuple[str, str]]:
    contract = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
    paths = contract.get("paths") or {}
    operations: set[tuple[str, str]] = set()
    for path, methods in paths.items():
        for method in methods:
            method_upper = str(method).upper()
            if method_upper in HTTP_METHODS:
                operations.add((path, method_upper))
    return operations
