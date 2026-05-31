"""Import permission and resource availability guard."""

from __future__ import annotations

import json
from typing import Any

from app.modules.import_pipeline.errors import ImportServiceError
from app.modules.import_pipeline.schemas import ImportActorContext
from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.service import PermissionService
from sqlalchemy import text
from sqlalchemy.orm import Session


class ImportPermissionGuard:
    """Validates import scope, resource availability and document permission scope."""

    def require_scope(
        self,
        actor_context: ImportActorContext | None,
        required_scope: str,
    ) -> None:
        if actor_context is None or not _has_scope(actor_context.scopes, required_scope):
            raise ImportServiceError(
                "IMPORT_SCOPE_REQUIRED",
                "current user does not include required scope",
                status_code=403,
                details={"required_scope": required_scope},
            )

    def load_knowledge_base(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
    ) -> dict[str, Any]:
        row = session.execute(
            text(
                """
                SELECT
                    kb.id::text AS kb_id,
                    kb.status,
                    kb.owner_department_id::text AS owner_department_id,
                    kb.kb_visibility,
                    kb.default_document_visibility,
                    kb.default_document_owner_department_id::text
                        AS default_document_owner_department_id,
                    COALESCE(
                        (
                            SELECT jsonb_agg(
                                jsonb_build_object(
                                    'subject_type', kba.subject_type,
                                    'subject_id', kba.subject_id::text,
                                    'permission', kba.permission
                                )
                                ORDER BY kba.subject_type, kba.subject_id::text, kba.permission
                            )
                            FROM knowledge_base_accesses kba
                            WHERE kba.enterprise_id = kb.enterprise_id
                              AND kba.kb_id = kb.id
                              AND kba.status = 'active'
                        ),
                        '[]'::jsonb
                    ) AS access_rules,
                    kb.policy_version
                FROM knowledge_bases kb
                WHERE kb.id = CAST(:kb_id AS uuid)
                  AND kb.enterprise_id = CAST(:enterprise_id AS uuid)
                  AND kb.deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "kb_id": kb_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_KB_NOT_FOUND",
                "knowledge base was not found",
                status_code=404,
                details={"kb_id": kb_id},
            )
        return dict(row._mapping)

    def ensure_actor_can_import_to_kb(
        self,
        actor_context: ImportActorContext | None,
        *,
        knowledge_base: dict[str, Any],
    ) -> None:
        if actor_context is None:
            return
        if _actor_can_import_to_kb(actor_context, knowledge_base=knowledge_base):
            return
        raise ImportServiceError(
            "IMPORT_KB_DENIED",
            "current user cannot import to the requested knowledge base",
            status_code=403,
            details={"kb_id": str(knowledge_base["kb_id"])},
        )

    def resolve_owner_department_id(
        self,
        session: Session,
        *,
        enterprise_id: str,
        requested_owner_department_id: str | None,
        default_document_owner_department_id: str,
        knowledge_base: dict[str, Any],
        actor_context: ImportActorContext | None,
    ) -> str:
        actor_department_id = (
            actor_context.department_ids[0]
            if actor_context and actor_context.department_ids
            else None
        )
        owner_department_id = (
            requested_owner_department_id
            or actor_department_id
            or default_document_owner_department_id
        )
        row = session.execute(
            text(
                """
                SELECT id::text AS department_id, status
                FROM departments
                WHERE id = CAST(:department_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "department_id": owner_department_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_NOT_FOUND",
                "owner department was not found",
                status_code=404,
                details={"owner_department_id": owner_department_id},
            )
        if row._mapping["status"] != "active":
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_UNAVAILABLE",
                "owner department is not active",
                status_code=409,
                details={
                    "owner_department_id": owner_department_id,
                    "status": row._mapping["status"],
                },
            )
        if (
            actor_context
            and owner_department_id not in actor_context.department_ids
            and not actor_context.can_import_all_knowledge_bases
            and not _actor_can_import_for_default_document_owner(
                actor_context,
                knowledge_base=knowledge_base,
                owner_department_id=owner_department_id,
                default_document_owner_department_id=default_document_owner_department_id,
            )
        ):
            raise ImportServiceError(
                "IMPORT_OWNER_DEPARTMENT_DENIED",
                "current user cannot import for the requested owner department",
                status_code=403,
                details={"owner_department_id": owner_department_id},
            )
        return owner_department_id

    def validate_visibility(self, *, owner_department_id: str, visibility: str) -> None:
        try:
            PermissionService().validate_visibility_policy(
                {"owner_department_id": owner_department_id, "visibility": visibility}
            )
        except PermissionServiceError as exc:
            raise ImportServiceError(
                exc.error_code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
                details=exc.details,
            ) from exc

    def ensure_document_permission_within_parent_knowledge_base(
        self,
        *,
        knowledge_base: dict[str, Any],
        visibility: str,
        owner_department_id: str,
    ) -> None:
        if visibility == "enterprise":
            return
        kb_id = str(knowledge_base.get("kb_id") or knowledge_base.get("id") or "")
        if not _department_can_query_knowledge_base(knowledge_base, owner_department_id):
            raise ImportServiceError(
                "IMPORT_DOCUMENT_PERMISSION_OUTSIDE_KB_SCOPE",
                "document owner department must be able to access parent knowledge base",
                status_code=409,
                details={
                    "kb_id": kb_id,
                    "kb_visibility": knowledge_base["kb_visibility"],
                    "kb_owner_department_id": knowledge_base["owner_department_id"],
                    "document_visibility": visibility,
                    "document_owner_department_id": owner_department_id,
                },
            )

    def ensure_folder_available(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        folder_id: str,
    ) -> None:
        row = session.execute(
            text(
                """
                SELECT id::text AS folder_id, status
                FROM folders
                WHERE id = CAST(:folder_id AS uuid)
                  AND kb_id = CAST(:kb_id AS uuid)
                  AND enterprise_id = CAST(:enterprise_id AS uuid)
                  AND deleted_at IS NULL
                """
            ),
            {"enterprise_id": enterprise_id, "kb_id": kb_id, "folder_id": folder_id},
        ).one_or_none()
        if row is None:
            raise ImportServiceError(
                "IMPORT_FOLDER_NOT_FOUND",
                "folder was not found",
                status_code=404,
                details={"folder_id": folder_id},
            )
        if row._mapping["status"] != "active":
            raise ImportServiceError(
                "IMPORT_FOLDER_UNAVAILABLE",
                "folder is not active",
                status_code=409,
                details={"folder_id": folder_id, "status": row._mapping["status"]},
            )


def _actor_can_import_to_kb(
    actor_context: ImportActorContext,
    *,
    knowledge_base: dict[str, Any],
) -> bool:
    if actor_context.can_import_all_knowledge_bases:
        return True
    kb_id = str(knowledge_base["kb_id"])
    if kb_id in actor_context.knowledge_base_ids:
        return True
    if _actor_has_kb_manage_access(actor_context, knowledge_base):
        return True
    return False


def _actor_can_import_for_default_document_owner(
    actor_context: ImportActorContext,
    *,
    knowledge_base: dict[str, Any],
    owner_department_id: str,
    default_document_owner_department_id: str,
) -> bool:
    return (
        owner_department_id == default_document_owner_department_id
        and _actor_can_import_to_kb(actor_context, knowledge_base=knowledge_base)
    )


def _department_can_query_knowledge_base(
    knowledge_base: dict[str, Any],
    department_id: str,
) -> bool:
    if knowledge_base["kb_visibility"] == "enterprise":
        return True
    return any(
        rule.get("subject_type") == "department"
        and rule.get("subject_id") == department_id
        and rule.get("permission") in {"query", "manage"}
        for rule in _kb_access_rule_dicts(knowledge_base)
    )


def _actor_has_kb_manage_access(
    actor_context: ImportActorContext,
    knowledge_base: dict[str, Any],
) -> bool:
    for rule in _kb_access_rule_dicts(knowledge_base):
        if rule.get("permission") != "manage":
            continue
        subject_type = rule.get("subject_type")
        subject_id = rule.get("subject_id")
        if subject_type == "user" and subject_id == actor_context.user_id:
            return True
        if subject_type == "department" and subject_id in actor_context.department_ids:
            return True
        if subject_type == "role" and subject_id in actor_context.role_ids:
            return True
    return False


def _kb_access_rule_dicts(knowledge_base: dict[str, Any]) -> list[dict[str, str]]:
    value = knowledge_base.get("access_rules") or []
    items = json.loads(value) if isinstance(value, str) else value
    if not isinstance(items, list):
        return []
    rules: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rules.append(
            {
                "subject_type": str(item.get("subject_type") or ""),
                "subject_id": str(item.get("subject_id") or ""),
                "permission": str(item.get("permission") or ""),
            }
        )
    return rules


def _has_scope(scopes: tuple[str, ...], required_scope: str) -> bool:
    if "*" in scopes or required_scope in scopes:
        return True
    prefix = required_scope.split(":", maxsplit=1)[0]
    return f"{prefix}:*" in scopes
