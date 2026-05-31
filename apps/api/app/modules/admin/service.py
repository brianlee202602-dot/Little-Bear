"""Admin service facade."""

from __future__ import annotations

from typing import Any

import app.modules.admin.access_control as admin_access_control
from app.modules.admin.access_control import AdminActorContext, RoleBindingInput
from app.modules.admin.departments_service import AdminDepartmentsService
from app.modules.admin.documents_service import AdminDocumentsService
from app.modules.admin.folder_document_counter import AdminFolderDocumentCounterMixin
from app.modules.admin.folders_service import AdminFoldersService
from app.modules.admin.index_job_writer import AdminIndexJobWriterMixin
from app.modules.admin.index_ops_service import AdminIndexOpsService
from app.modules.admin.index_target_reader import AdminIndexTargetReader
from app.modules.admin.knowledge_bases_service import AdminKnowledgeBasesService
from app.modules.admin.permission_admin_service import AdminPermissionService
from app.modules.admin.permission_guard import AdminPermissionGuardMixin
from app.modules.admin.permission_version_reader import AdminPermissionVersionReader
from app.modules.admin.permission_writer import AdminPermissionWriterMixin
from app.modules.admin.resource_loaders import AdminResourceLoaderMixin
from app.modules.admin.role_binding_reader import AdminRoleBindingReader
from app.modules.admin.role_binding_writer import AdminRoleBindingWriterMixin
from app.modules.admin.role_policy import _is_high_risk_role, _merge_scopes
from app.modules.admin.roles_service import AdminRolesService
from app.modules.admin.state_writer import AdminStateWriterMixin
from app.modules.admin.users_service import AdminUsersService
from app.modules.auth.password_service import PasswordService
from app.modules.storage.service import ObjectStorage


class AdminService(
    admin_access_control.AdminAccessControlMixin,
    AdminResourceLoaderMixin,
    AdminPermissionGuardMixin,
    AdminFolderDocumentCounterMixin,
    AdminRoleBindingWriterMixin,
    AdminPermissionWriterMixin,
    AdminIndexJobWriterMixin,
    AdminStateWriterMixin,
):
    """Route-facing admin facade.

    Domain workflows live in the dedicated admin services. Shared admin helpers
    are composed here directly instead of through a transitional core module.
    """

    def __init__(
        self,
        *,
        password_service: PasswordService | None = None,
        object_storage: ObjectStorage | None = None,
        role_binding_reader: AdminRoleBindingReader | None = None,
        permission_version_reader: AdminPermissionVersionReader | None = None,
        index_target_reader: AdminIndexTargetReader | None = None,
    ) -> None:
        self.password_service = password_service or PasswordService()
        self.object_storage = object_storage
        self.role_binding_reader = role_binding_reader or AdminRoleBindingReader()
        self.permission_version_reader = (
            permission_version_reader or AdminPermissionVersionReader()
        )
        self.index_target_reader = index_target_reader or AdminIndexTargetReader()

    def list_users(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().list_users(*args, **kwargs)

    def get_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().get_user(*args, **kwargs)

    def create_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().create_user(*args, **kwargs)

    def patch_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().patch_user(*args, **kwargs)

    def delete_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().delete_user(*args, **kwargs)

    def reset_user_password(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().reset_user_password(*args, **kwargs)

    def unlock_user(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().unlock_user(*args, **kwargs)

    def list_user_departments(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().list_user_departments(*args, **kwargs)

    def replace_user_departments(self, *args: Any, **kwargs: Any) -> Any:
        return self._users().replace_user_departments(*args, **kwargs)

    def list_departments(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().list_departments(*args, **kwargs)

    def list_department_options(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().list_department_options(*args, **kwargs)

    def get_department(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().get_department(*args, **kwargs)

    def create_department(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().create_department(*args, **kwargs)

    def patch_department(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().patch_department(*args, **kwargs)

    def delete_department(self, *args: Any, **kwargs: Any) -> Any:
        return self._departments().delete_department(*args, **kwargs)

    def list_knowledge_bases(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().list_knowledge_bases(*args, **kwargs)

    def list_knowledge_base_options(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().list_knowledge_base_options(*args, **kwargs)

    def get_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().get_knowledge_base(*args, **kwargs)

    def create_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().create_knowledge_base(*args, **kwargs)

    def patch_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().patch_knowledge_base(*args, **kwargs)

    def delete_knowledge_base(self, *args: Any, **kwargs: Any) -> Any:
        return self._knowledge_bases().delete_knowledge_base(*args, **kwargs)

    def list_folders(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().list_folders(*args, **kwargs)

    def list_folder_options(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().list_folder_options(*args, **kwargs)

    def get_folder(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().get_folder(*args, **kwargs)

    def create_folder(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().create_folder(*args, **kwargs)

    def patch_folder(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().patch_folder(*args, **kwargs)

    def delete_folder(self, *args: Any, **kwargs: Any) -> Any:
        return self._folders().delete_folder(*args, **kwargs)

    def list_documents(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().list_documents(*args, **kwargs)

    def get_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().get_document(*args, **kwargs)

    def patch_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().patch_document(*args, **kwargs)

    def delete_document(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().delete_document(*args, **kwargs)

    def list_document_versions(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().list_document_versions(*args, **kwargs)

    def list_document_chunks(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().list_document_chunks(*args, **kwargs)

    def get_document_preview(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().get_document_preview(*args, **kwargs)

    def list_document_index_versions(self, *args: Any, **kwargs: Any) -> Any:
        return self._documents().list_document_index_versions(*args, **kwargs)

    def create_document_index_rebuild_job(self, *args: Any, **kwargs: Any) -> Any:
        return self._index_ops().create_document_index_rebuild_job(*args, **kwargs)

    def create_index_rebuild_job(self, *args: Any, **kwargs: Any) -> Any:
        return self._index_ops().create_index_rebuild_job(*args, **kwargs)

    def create_collection_index_rebuild_job(self, *args: Any, **kwargs: Any) -> Any:
        return self._index_ops().create_collection_index_rebuild_job(*args, **kwargs)

    def create_index_version_cleanup_job(self, *args: Any, **kwargs: Any) -> Any:
        return self._index_ops().create_index_version_cleanup_job(*args, **kwargs)

    def replace_knowledge_base_permissions(self, *args: Any, **kwargs: Any) -> Any:
        return self._permissions().replace_knowledge_base_permissions(*args, **kwargs)

    def replace_document_permissions(self, *args: Any, **kwargs: Any) -> Any:
        return self._permissions().replace_document_permissions(*args, **kwargs)

    def list_roles(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().list_roles(*args, **kwargs)

    def list_assignable_role_options(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().list_assignable_role_options(*args, **kwargs)

    def get_role(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().get_role(*args, **kwargs)

    def list_role_bindings(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().list_role_bindings(*args, **kwargs)

    def create_role_bindings(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().create_role_bindings(*args, **kwargs)

    def replace_role_bindings(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().replace_role_bindings(*args, **kwargs)

    def revoke_role_binding(self, *args: Any, **kwargs: Any) -> Any:
        return self._roles().revoke_role_binding(*args, **kwargs)

    def _users(self) -> AdminUsersService:
        return AdminUsersService(self)

    def _departments(self) -> AdminDepartmentsService:
        return AdminDepartmentsService(self)

    def _knowledge_bases(self) -> AdminKnowledgeBasesService:
        return AdminKnowledgeBasesService(self)

    def _folders(self) -> AdminFoldersService:
        return AdminFoldersService(self)

    def _documents(self) -> AdminDocumentsService:
        return AdminDocumentsService(self)

    def _index_ops(self) -> AdminIndexOpsService:
        return AdminIndexOpsService(self)

    def _permissions(self) -> AdminPermissionService:
        return AdminPermissionService(self)

    def _roles(self) -> AdminRolesService:
        return AdminRolesService(self)


__all__ = [
    "AdminActorContext",
    "AdminService",
    "RoleBindingInput",
    "_is_high_risk_role",
    "_merge_scopes",
]
