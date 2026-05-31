"""权限策略校验与快照构建。"""

from __future__ import annotations

from typing import Any

from app.modules.permissions.errors import PermissionServiceError
from app.shared.json_utils import stable_json_hash

SUPPORTED_VISIBILITIES = {"department", "enterprise"}
UNSUPPORTED_POLICY_KEYS = {
    "user_ids",
    "project_ids",
    "group_ids",
    "custom_org_ids",
    "acl_entries",
    "allow_users",
    "deny_users",
    "recursive_departments",
    "include_child_departments",
    "include_parent_departments",
}


class PermissionPolicyValidator:
    """校验 P0 文档可见性策略并生成索引快照 payload。"""

    def validate_visibility_policy(self, policy: dict[str, Any]) -> None:
        unsupported = sorted(UNSUPPORTED_POLICY_KEYS.intersection(policy))
        if unsupported:
            raise PermissionServiceError(
                "UNSUPPORTED_PERMISSION_POLICY",
                "P0 permission policy only supports visibility and owner_department_id",
                status_code=400,
                details={"unsupported_keys": unsupported},
            )
        visibility = policy.get("visibility")
        if visibility not in SUPPORTED_VISIBILITIES:
            raise PermissionServiceError(
                "PERM_VISIBILITY_INVALID",
                "document visibility must be department or enterprise",
                status_code=400,
                details={"visibility": visibility},
            )
        owner_department_id = policy.get("owner_department_id")
        if visibility == "department" and not owner_department_id:
            raise PermissionServiceError(
                "PERM_POLICY_INVALID",
                "department visibility requires owner_department_id",
                status_code=400,
            )

    def build_permission_snapshot_payload(
        self,
        *,
        owner_department_id: str,
        visibility: str,
        permission_version: int,
        policy_version: int,
    ) -> dict[str, Any]:
        self.validate_visibility_policy(
            {"owner_department_id": owner_department_id, "visibility": visibility}
        )
        payload = {
            "owner_department_id": owner_department_id,
            "visibility": visibility,
            "permission_version": permission_version,
            "policy_version": policy_version,
        }
        return {
            "payload": payload,
            "payload_hash": stable_json_hash(payload),
        }
