"""权限模块。"""

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
    "PermissionContext",
    "PermissionDepartment",
    "PermissionFilter",
    "PermissionRole",
    "PermissionService",
    "PermissionServiceError",
]
