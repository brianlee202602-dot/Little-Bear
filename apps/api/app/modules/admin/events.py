"""Audit event helpers for admin resource updates."""

from __future__ import annotations


def _knowledge_base_update_event(
    *,
    before_status: str,
    after_status: str,
) -> tuple[str, str, str]:
    if before_status != after_status and after_status == "disabled":
        return "knowledge_base.disabled", "disable", "high"
    if before_status != after_status and after_status == "archived":
        return "knowledge_base.archived", "archive", "medium"
    if before_status != after_status and after_status == "active":
        return "knowledge_base.restored", "restore", "medium"
    return "knowledge_base.updated", "update", "medium"


def _folder_update_event(
    *,
    before_status: str,
    after_status: str,
    moved: bool,
) -> tuple[str, str, str]:
    if moved:
        return "folder.moved", "move", "medium"
    if before_status != after_status and after_status == "disabled":
        return "folder.disabled", "disable", "medium"
    if before_status != after_status and after_status == "archived":
        return "folder.archived", "archive", "low"
    return "folder.updated", "update", "low"


def _document_update_event(
    *,
    before_status: str,
    after_status: str,
    visibility_expanded: bool,
    permission_tightened: bool,
) -> tuple[str, str, str]:
    if permission_tightened:
        return "document.permission_tightened", "tighten_permission", "critical"
    if visibility_expanded:
        return "document.visibility_expanded", "expand_visibility", "high"
    if before_status != after_status and after_status == "archived":
        return "document.archived", "archive", "medium"
    if before_status != after_status and after_status == "active":
        return "document.restored", "restore", "medium"
    return "document.updated", "update", "medium"


def _changed_update_fields(updates: list[str]) -> list[str]:
    changed_fields: list[str] = []
    for update in updates:
        field = update.split(" = ", 1)[0]
        if field == "permission_snapshot_id":
            continue
        changed_fields.append(field)
    return changed_fields
