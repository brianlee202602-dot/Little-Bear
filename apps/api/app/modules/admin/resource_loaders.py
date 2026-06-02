"""Shared resource loader helpers for admin services."""

from __future__ import annotations

from typing import Any

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.mappers import (
    _document_from_mapping,
    _folder_from_mapping,
    _IndexCleanupTarget,
    _IndexRebuildTarget,
    _knowledge_base_access_rules_sql,
    _knowledge_base_from_mapping,
    _role_from_mapping,
)
from app.modules.admin.schemas import (
    AdminDepartment,
    AdminDocument,
    AdminFolder,
    AdminKnowledgeBase,
    AdminRole,
    AdminRoleBinding,
)
from app.modules.admin.utils import _database_error, _normalize_id_list
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


class AdminResourceLoaderMixin:
    """管理后台领域服务共享的资源读取 helper。"""

    def _load_user_row(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> dict[str, Any]:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS user_id,
                        enterprise_id::text AS enterprise_id,
                        username,
                        display_name,
                        email,
                        phone,
                        status
                    FROM users
                    WHERE id = CAST(:user_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                    LIMIT 1
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_USER_UNAVAILABLE", "user cannot be read", exc) from exc
        if row is None:
            raise AdminServiceError("ADMIN_USER_NOT_FOUND", "user does not exist", status_code=404)
        return dict(row._mapping)

    def _load_knowledge_base(
        self,
        session: Session,
        kb_id: str,
        *,
        enterprise_id: str,
    ) -> AdminKnowledgeBase:
        try:
            row = session.execute(
                text(
                    f"""
                    SELECT
                        knowledge_bases.id::text AS kb_id,
                        knowledge_bases.name,
                        knowledge_bases.status,
                        knowledge_bases.owner_department_id::text AS owner_department_id,
                        owner_department.code AS owner_department_code,
                        owner_department.name AS owner_department_name,
                        owner_department.status AS owner_department_status,
                        owner_department.is_default AS owner_department_is_default,
                        knowledge_bases.kb_visibility,
                        knowledge_bases.default_document_visibility,
                        knowledge_bases.default_document_owner_department_id::text
                            AS default_document_owner_department_id,
                        default_document_owner_department.code
                            AS default_document_owner_department_code,
                        default_document_owner_department.name
                            AS default_document_owner_department_name,
                        default_document_owner_department.status
                            AS default_document_owner_department_status,
                        default_document_owner_department.is_default
                            AS default_document_owner_department_is_default,
                        {_knowledge_base_access_rules_sql("knowledge_bases.id")},
                        knowledge_bases.config_scope_id,
                        knowledge_bases.policy_version
                    FROM knowledge_bases
                    LEFT JOIN departments owner_department
                      ON owner_department.id = knowledge_bases.owner_department_id
                     AND owner_department.enterprise_id = knowledge_bases.enterprise_id
                     AND owner_department.deleted_at IS NULL
                    LEFT JOIN departments default_document_owner_department
                      ON default_document_owner_department.id =
                         knowledge_bases.default_document_owner_department_id
                     AND default_document_owner_department.enterprise_id =
                         knowledge_bases.enterprise_id
                     AND default_document_owner_department.deleted_at IS NULL
                    WHERE knowledge_bases.id = CAST(:kb_id AS uuid)
                      AND knowledge_bases.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND knowledge_bases.deleted_at IS NULL
                      AND knowledge_bases.status != 'deleted'
                    LIMIT 1
                    """
                ),
                {"kb_id": kb_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_KNOWLEDGE_BASE_UNAVAILABLE",
                "knowledge base cannot be read",
                exc,
            ) from exc
        if row is None:
            raise AdminServiceError(
                "ADMIN_KNOWLEDGE_BASE_NOT_FOUND",
                "knowledge base does not exist",
                status_code=404,
            )
        return _knowledge_base_from_mapping(row._mapping)

    def _load_folder(
        self,
        session: Session,
        folder_id: str,
        *,
        enterprise_id: str,
    ) -> AdminFolder:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS folder_id,
                        kb_id::text AS kb_id,
                        parent_id::text AS parent_id,
                        name,
                        path,
                        status
                    FROM folders
                    WHERE id = CAST(:folder_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                      AND deleted_at IS NULL
                      AND status != 'deleted'
                    LIMIT 1
                    """
                ),
                {"folder_id": folder_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_FOLDER_UNAVAILABLE",
                "folder cannot be read",
                exc,
            ) from exc
        if row is None:
            raise AdminServiceError(
                "ADMIN_FOLDER_NOT_FOUND",
                "folder does not exist",
                status_code=404,
            )
        return _folder_from_mapping(row._mapping)

    def _load_document(
        self,
        session: Session,
        doc_id: str,
        *,
        enterprise_id: str,
    ) -> AdminDocument:
        try:
            row = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS doc_id,
                        d.kb_id::text AS kb_id,
                        d.folder_id::text AS folder_id,
                        d.title,
                        d.lifecycle_status,
                        d.index_status,
                        d.owner_department_id::text AS owner_department_id,
                        d.visibility,
                        d.current_version_id::text AS current_version_id,
                        dv.version_no AS current_version_no,
                        d.tags,
                        d.permission_snapshot_id::text AS permission_snapshot_id,
                        d.content_hash,
                        COALESCE(ps.policy_version, 1) AS policy_version
                    FROM documents d
                    LEFT JOIN permission_snapshots ps ON ps.id = d.permission_snapshot_id
                    LEFT JOIN document_versions dv ON dv.id = d.current_version_id
                    WHERE d.id = CAST(:doc_id AS uuid)
                      AND d.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND d.deleted_at IS NULL
                      AND d.lifecycle_status != 'deleted'
                    LIMIT 1
                    """
                ),
                {"doc_id": doc_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_DOCUMENT_UNAVAILABLE",
                "document cannot be read",
                exc,
            ) from exc
        if row is None:
            raise AdminServiceError(
                "ADMIN_DOCUMENT_NOT_FOUND",
                "document does not exist",
                status_code=404,
            )
        return _document_from_mapping(row._mapping)

    def _load_user_roles(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> tuple[AdminRole, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        r.id::text AS role_id,
                        r.code,
                        r.name,
                        r.scope_type,
                        r.scopes,
                        r.is_builtin,
                        r.status
                    FROM role_bindings rb
                    JOIN roles r ON r.id = rb.role_id
                    WHERE rb.user_id = CAST(:user_id AS uuid)
                      AND rb.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND rb.status = 'active'
                      AND r.status = 'active'
                    ORDER BY r.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_ROLES_UNAVAILABLE",
                "user roles cannot be read",
                exc,
            ) from exc
        return tuple(_role_from_mapping(row._mapping) for row in rows)

    def _load_user_departments(
        self,
        session: Session,
        user_id: str,
        *,
        enterprise_id: str,
    ) -> tuple[AdminDepartment, ...]:
        try:
            rows = session.execute(
                text(
                    """
                    SELECT
                        d.id::text AS department_id,
                        d.code,
                        d.name,
                        d.status,
                        udm.is_primary,
                        d.is_default
                    FROM user_department_memberships udm
                    JOIN departments d ON d.id = udm.department_id
                    WHERE udm.user_id = CAST(:user_id AS uuid)
                      AND udm.enterprise_id = CAST(:enterprise_id AS uuid)
                      AND udm.status = 'active'
                    ORDER BY udm.is_primary DESC, d.code
                    """
                ),
                {"user_id": user_id, "enterprise_id": enterprise_id},
            ).all()
        except SQLAlchemyError as exc:
            raise _database_error(
                "ADMIN_USER_DEPARTMENTS_UNAVAILABLE",
                "user departments cannot be read",
                exc,
            ) from exc
        return tuple(
            AdminDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_primary=bool(row._mapping["is_primary"]),
                is_default=bool(row._mapping["is_default"]),
            )
            for row in rows
        )

    def _resolve_departments(
        self,
        session: Session,
        *,
        enterprise_id: str,
        department_ids: list[str],
    ) -> list[AdminDepartment]:
        if not department_ids:
            row = session.execute(
                text(
                    """
                    SELECT
                        id::text AS department_id,
                        code,
                        name,
                        status,
                        true AS is_primary,
                        is_default
                    FROM departments
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND is_default = true
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
            if row is None:
                raise AdminServiceError(
                    "ADMIN_DEFAULT_DEPARTMENT_MISSING",
                    "default department is missing",
                    status_code=409,
                )
            return [
                AdminDepartment(
                    id=row._mapping["department_id"],
                    code=row._mapping["code"],
                    name=row._mapping["name"],
                    status=row._mapping["status"],
                    is_primary=True,
                    is_default=bool(row._mapping["is_default"]),
                )
            ]

        normalized_department_ids = _normalize_id_list(department_ids)
        if len(normalized_department_ids) != len(department_ids):
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_INVALID",
                "department ids must be unique and non-empty",
                status_code=400,
            )
        rows = session.execute(
            text(
                """
                SELECT id::text AS department_id, code, name, status, is_default
                FROM departments
                WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                  AND id = ANY(CAST(:department_ids AS uuid[]))
                  AND status = 'active'
                ORDER BY code
                """
            ),
            {"enterprise_id": enterprise_id, "department_ids": normalized_department_ids},
        ).all()
        if len(rows) != len(normalized_department_ids):
            raise AdminServiceError(
                "ADMIN_DEPARTMENT_NOT_FOUND",
                "one or more departments do not exist",
                status_code=404,
            )
        departments_by_id = {
            row._mapping["department_id"]: AdminDepartment(
                id=row._mapping["department_id"],
                code=row._mapping["code"],
                name=row._mapping["name"],
                status=row._mapping["status"],
                is_default=bool(row._mapping["is_default"]),
            )
            for row in rows
        }
        return [departments_by_id[department_id] for department_id in normalized_department_ids]

    def _resolve_department(
        self,
        session: Session,
        *,
        enterprise_id: str,
        department_id: str,
    ) -> AdminDepartment:
        rows = self._resolve_departments(
            session,
            enterprise_id=enterprise_id,
            department_ids=[department_id],
        )
        return rows[0]

    def _resolve_parent_folder(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        parent_id: str | None,
    ) -> AdminFolder | None:
        if parent_id is None:
            return None
        parent = self._load_folder(session, parent_id, enterprise_id=enterprise_id)
        if parent.kb_id != kb_id:
            raise AdminServiceError(
                "ADMIN_FOLDER_PARENT_INVALID",
                "parent folder is outside knowledge base",
                status_code=409,
                details={"parent_id": parent_id, "kb_id": kb_id},
            )
        if parent.status != "active":
            raise AdminServiceError(
                "ADMIN_FOLDER_PARENT_INVALID",
                "parent folder must be active",
                status_code=409,
                details={"parent_id": parent_id, "status": parent.status},
            )
        return parent

    def _resolve_document_folder(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
        folder_id: str | None,
    ) -> AdminFolder | None:
        if folder_id is None:
            return None
        folder = self._load_folder(session, folder_id, enterprise_id=enterprise_id)
        if folder.kb_id != kb_id:
            raise AdminServiceError(
                "ADMIN_DOCUMENT_FOLDER_INVALID",
                "document folder is outside knowledge base",
                status_code=409,
                details={"folder_id": folder_id, "kb_id": kb_id},
            )
        if folder.status != "active":
            raise AdminServiceError(
                "ADMIN_DOCUMENT_FOLDER_INVALID",
                "document folder must be active",
                status_code=409,
                details={"folder_id": folder_id, "status": folder.status},
            )
        return folder

    def _resolve_roles(
        self,
        session: Session,
        *,
        enterprise_id: str,
        role_ids: list[str],
    ) -> list[AdminRole]:
        if not role_ids:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS role_id
                    FROM roles
                    WHERE enterprise_id = CAST(:enterprise_id AS uuid)
                      AND code = 'employee'
                      AND status = 'active'
                    LIMIT 1
                    """
                ),
                {"enterprise_id": enterprise_id},
            ).one_or_none()
            if row is None:
                raise AdminServiceError(
                    "ADMIN_DEFAULT_ROLE_MISSING",
                    "default employee role is missing",
                    status_code=409,
                )
            role_ids = [row._mapping["role_id"]]
        roles = [
            self._load_role(session, role_id, enterprise_id=enterprise_id) for role_id in role_ids
        ]
        inactive_roles = [role.code for role in roles if role.status != "active"]
        if inactive_roles:
            raise AdminServiceError(
                "ADMIN_ROLE_INACTIVE",
                "inactive roles cannot be granted",
                status_code=409,
                details={"role_codes": inactive_roles},
            )
        return roles

    def _load_role(self, session: Session, role_id: str, *, enterprise_id: str) -> AdminRole:
        try:
            row = session.execute(
                text(
                    """
                    SELECT id::text AS role_id, code, name, scope_type, scopes, is_builtin, status
                    FROM roles
                    WHERE id = CAST(:role_id AS uuid)
                      AND enterprise_id = CAST(:enterprise_id AS uuid)
                    LIMIT 1
                    """
                ),
                {"role_id": role_id, "enterprise_id": enterprise_id},
            ).one_or_none()
        except SQLAlchemyError as exc:
            raise _database_error("ADMIN_ROLE_UNAVAILABLE", "role cannot be read", exc) from exc
        if row is None:
            raise AdminServiceError("ADMIN_ROLE_NOT_FOUND", "role does not exist", status_code=404)
        return _role_from_mapping(row._mapping)

    def _load_role_bindings(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
    ) -> list[AdminRoleBinding]:
        return self.role_binding_reader.load_role_bindings(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
        )

    def _load_role_binding(
        self,
        session: Session,
        *,
        enterprise_id: str,
        user_id: str,
        binding_id: str,
    ) -> AdminRoleBinding:
        return self.role_binding_reader.load_role_binding(
            session,
            enterprise_id=enterprise_id,
            user_id=user_id,
            binding_id=binding_id,
        )

    def _load_resource_permission_version(
        self,
        session: Session,
        *,
        enterprise_id: str,
        resource_type: str,
        resource_id: str,
    ) -> int:
        return self.permission_version_reader.load_resource_permission_version(
            session,
            enterprise_id=enterprise_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )

    def _load_index_rebuild_targets_for_kb(
        self,
        session: Session,
        *,
        enterprise_id: str,
        kb_id: str,
    ) -> list[_IndexRebuildTarget]:
        return self.index_target_reader.load_rebuild_targets_for_kb(
            session,
            enterprise_id=enterprise_id,
            kb_id=kb_id,
        )

    def _load_index_rebuild_targets_for_documents(
        self,
        session: Session,
        *,
        enterprise_id: str,
        document_ids: list[str],
    ) -> list[_IndexRebuildTarget]:
        return self.index_target_reader.load_rebuild_targets_for_documents(
            session,
            enterprise_id=enterprise_id,
            document_ids=document_ids,
        )

    def _load_index_rebuild_targets_for_collection(
        self,
        session: Session,
        *,
        enterprise_id: str,
        collection_name: str,
    ) -> list[_IndexRebuildTarget]:
        return self.index_target_reader.load_rebuild_targets_for_collection(
            session,
            enterprise_id=enterprise_id,
            collection_name=collection_name,
        )

    def _load_index_cleanup_targets(
        self,
        session: Session,
        *,
        enterprise_id: str,
        index_version_ids: list[str],
    ) -> list[_IndexCleanupTarget]:
        return self.index_target_reader.load_cleanup_targets(
            session,
            enterprise_id=enterprise_id,
            index_version_ids=index_version_ids,
        )
