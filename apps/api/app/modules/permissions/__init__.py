"""权限模块。"""

from app.modules.permissions.admin_schemas import (
    PermissionAdminActorContext,
    PermissionKnowledgeBaseAccessRule,
    PermissionKnowledgeBaseAccessRuleInput,
    PermissionKnowledgeBasePolicy,
    PermissionPolicy,
)
from app.modules.permissions.admin_service import PermissionAdminService
from app.modules.permissions.errors import PermissionServiceError
from app.modules.permissions.schemas import (
    CandidateGateResult,
    CandidateMetadata,
    PermissionContext,
    PermissionDepartment,
    PermissionFilter,
    PermissionRole,
)
from app.modules.permissions.service import PermissionService

__all__ = [
    "CandidateGateResult",
    "CandidateMetadata",
    "PermissionAdminActorContext",
    "PermissionContext",
    "PermissionDepartment",
    "PermissionFilter",
    "PermissionKnowledgeBaseAccessRule",
    "PermissionKnowledgeBaseAccessRuleInput",
    "PermissionKnowledgeBasePolicy",
    "PermissionPolicy",
    "PermissionRole",
    "PermissionAdminService",
    "PermissionService",
    "PermissionServiceError",
]
