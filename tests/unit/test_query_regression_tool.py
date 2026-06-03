from __future__ import annotations

import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import query_regression  # noqa: E402


def test_case_from_mapping_preserves_explicit_empty_kb_ids_for_auto_scope() -> None:
    query_case = query_regression._case_from_mapping(
        {
            "case_id": "auto_scope",
            "kb_ids": [],
            "query": "什么是 RAG",
        },
        default_kb_ids=["default-kb"],
        knowledge_bases=[{"id": "dev-kb", "name": "开发指南"}],
    )

    assert query_case.kb_ids == []


def test_case_from_mapping_uses_default_kb_when_kb_ids_omitted() -> None:
    query_case = query_regression._case_from_mapping(
        {
            "case_id": "default_scope",
            "query": "什么是 RAG",
        },
        default_kb_ids=["default-kb"],
        knowledge_bases=[{"id": "dev-kb", "name": "开发指南"}],
    )

    assert query_case.kb_ids == ["default-kb"]
