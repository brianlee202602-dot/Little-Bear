"""Admin management module."""

from app.modules.admin.errors import AdminServiceError
from app.modules.admin.index_target_reader import AdminIndexTargetReader
from app.modules.admin.permission_version_reader import AdminPermissionVersionReader
from app.modules.admin.role_binding_reader import AdminRoleBindingReader
from app.modules.admin.schemas import (
    AdminAssignableRoleOption,
    AdminAssignableRoleOptionList,
    AdminDepartment,
    AdminDepartmentList,
    AdminDepartmentListItem,
    AdminDepartmentOption,
    AdminDepartmentOptionList,
    AdminFolder,
    AdminFolderList,
    AdminFolderOption,
    AdminFolderOptionList,
    AdminKnowledgeBaseListItem,
    AdminKnowledgeBaseOption,
    AdminKnowledgeBaseOptionList,
    AdminRole,
    AdminRoleBinding,
    AdminRoleList,
    AdminRoleListItem,
    AdminUser,
    AdminUserList,
)
from app.modules.admin.service import AdminActorContext, AdminService, RoleBindingInput

__all__ = [
    "AdminActorContext",
    "AdminDepartment",
    "AdminDepartmentList",
    "AdminDepartmentListItem",
    "AdminDepartmentOption",
    "AdminDepartmentOptionList",
    "AdminFolder",
    "AdminFolderList",
    "AdminFolderOption",
    "AdminFolderOptionList",
    "AdminIndexTargetReader",
    "AdminKnowledgeBaseListItem",
    "AdminKnowledgeBaseOption",
    "AdminKnowledgeBaseOptionList",
    "AdminPermissionVersionReader",
    "AdminAssignableRoleOption",
    "AdminAssignableRoleOptionList",
    "AdminRoleBindingReader",
    "AdminRole",
    "AdminRoleList",
    "AdminRoleListItem",
    "AdminRoleBinding",
    "AdminService",
    "AdminServiceError",
    "AdminUser",
    "AdminUserList",
    "RoleBindingInput",
]
