from __future__ import annotations

from pathlib import Path

import yaml
from app.main import create_app

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
CONTRACT_PATH = Path("docs/contracts/openapi.yaml")

# OpenAPI 中已经冻结、但当前后端尚未挂载的 P0/P1 契约。后续每实现一个接口，
# 都应从这里删除对应项，让测试成为开发进度的细颗粒提醒。
EXPECTED_CONTRACT_ONLY_OPERATIONS = {
    ("/internal/v1/admin/documents/{doc_id}/chunks", "GET"),
    ("/internal/v1/admin/documents/{doc_id}/index-jobs", "POST"),
    ("/internal/v1/admin/documents/{doc_id}/index-versions", "GET"),
    ("/internal/v1/admin/documents/{doc_id}/versions", "GET"),
    ("/internal/v1/admin/import-jobs", "GET"),
    ("/internal/v1/admin/import-jobs/{job_id}", "GET"),
    ("/internal/v1/admin/model-call-logs", "GET"),
    ("/internal/v1/admin/query-logs", "GET"),
    ("/internal/v1/admin/query-logs/{query_log_id}", "GET"),
    ("/internal/v1/admin/roles", "POST"),
    ("/internal/v1/admin/roles/{role_id}", "DELETE"),
    ("/internal/v1/admin/roles/{role_id}", "PATCH"),
    ("/internal/v1/documents/{doc_id}", "GET"),
    ("/internal/v1/documents/{doc_id}/chunks", "GET"),
    ("/internal/v1/documents/{doc_id}/permissions", "PUT"),
    ("/internal/v1/documents/{doc_id}/preview", "GET"),
    ("/internal/v1/documents/{doc_id}/versions", "GET"),
    ("/internal/v1/import-jobs/{job_id}", "GET"),
    ("/internal/v1/import-jobs/{job_id}", "PATCH"),
    ("/internal/v1/import-jobs/{job_id}/retries", "POST"),
    ("/internal/v1/knowledge-bases", "GET"),
    ("/internal/v1/knowledge-bases/{kb_id}", "GET"),
    ("/internal/v1/knowledge-bases/{kb_id}/document-imports", "POST"),
    ("/internal/v1/knowledge-bases/{kb_id}/documents", "GET"),
    ("/internal/v1/knowledge-bases/{kb_id}/documents", "POST"),
    ("/internal/v1/knowledge-bases/{kb_id}/folders", "GET"),
    ("/internal/v1/knowledge-bases/{kb_id}/permissions", "PUT"),
    ("/internal/v1/model-catalog", "GET"),
    ("/internal/v1/model-chat-completions", "POST"),
    ("/internal/v1/model-embeddings", "POST"),
    ("/internal/v1/model-health", "GET"),
    ("/internal/v1/model-rerankings", "POST"),
    ("/internal/v1/permission-evaluations", "GET"),
    ("/internal/v1/queries", "POST"),
    ("/internal/v1/query-streams", "POST"),
}


def test_all_implemented_routes_are_declared_in_openapi_contract() -> None:
    undocumented = _actual_operations() - _contract_operations()

    assert undocumented == set()


def test_contract_only_operations_match_tracked_gap() -> None:
    contract_only = _contract_operations() - _actual_operations()

    assert contract_only == EXPECTED_CONTRACT_ONLY_OPERATIONS


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
