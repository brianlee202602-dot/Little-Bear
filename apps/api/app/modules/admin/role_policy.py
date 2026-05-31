"""Role policy helpers for admin services."""

from __future__ import annotations

from app.modules.admin.schemas import AdminRole, AdminUser

HIGH_RISK_ROLE_CODES = {"system_admin", "security_admin", "audit_admin"}
HIGH_RISK_SCOPE_EXACT = {
    "config:manage",
    "user:manage",
    "role:manage",
    "permission:manage",
}
HIGH_RISK_SCOPE_PREFIXES = ("config:", "user:", "role:", "permission:")


def _merge_scopes(roles: tuple[AdminRole, ...]) -> tuple[str, ...]:
    scopes = {"auth:session", "auth:password:update:self"}
    for role in roles:
        scopes.update(role.scopes)
    return tuple(sorted(scopes))


def _is_high_risk_role(role: AdminRole) -> bool:
    if role.code in HIGH_RISK_ROLE_CODES or "*" in role.scopes:
        return True
    return any(_is_high_risk_scope(scope) for scope in role.scopes)


def _is_high_risk_scope(scope: str) -> bool:
    if scope in HIGH_RISK_SCOPE_EXACT:
        return True
    if scope.endswith(":*") and scope.removesuffix(":*") in {
        "config",
        "user",
        "role",
        "permission",
    }:
        return True
    return any(
        scope.startswith(prefix) and scope.endswith(":manage")
        for prefix in HIGH_RISK_SCOPE_PREFIXES
    )


def _has_system_admin(user: AdminUser) -> bool:
    return any(role.code == "system_admin" for role in user.roles)
