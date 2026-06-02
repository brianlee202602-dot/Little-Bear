import type {
  AdminAssignableRoleOptionData,
  AdminRoleBindingData,
  AdminRoleData,
} from "@/api/roles";
export {
  builtinRoleLabels,
  formatRoleCodeLabel,
  formatRoleLabel,
  formatRoleList,
} from "@/utils/roles";

export function formatRoleScopeType(scopeType: string | null | undefined): string {
  if (scopeType === "enterprise") {
    return "企业级";
  }
  if (scopeType === "department") {
    return "部门级";
  }
  if (scopeType === "knowledge_base") {
    return "知识库级";
  }
  return scopeType || "-";
}

export function roleBindingKey(binding: AdminRoleBindingData): string {
  return roleBindingKeyFromParts(binding.role_id, binding.scope_type, binding.scope_id);
}

export function roleBindingKeyFromParts(
  roleId: string,
  scopeType: "enterprise" | "department" | "knowledge_base",
  scopeId: string | null,
): string {
  return `${roleId}:${scopeType}:${scopeType === "enterprise" ? "enterprise" : scopeId ?? ""}`;
}

export function formatRoleBindingScope(
  binding: AdminRoleBindingData,
  lookups: {
    formatDepartmentById: (departmentId: string | null | undefined) => string;
    formatKnowledgeBaseById: (knowledgeBaseId: string | null | undefined) => string;
  },
): string {
  if (binding.scope_type === "enterprise") {
    return "全企业";
  }
  if (binding.scope_type === "department") {
    return `部门：${lookups.formatDepartmentById(binding.scope_id)}`;
  }
  return `知识库：${lookups.formatKnowledgeBaseById(binding.scope_id)}`;
}

export function isHighRiskAdminRole(
  role: AdminAssignableRoleOptionData | AdminRoleData,
): boolean {
  if ("risk_level" in role) {
    return role.risk_level === "high";
  }
  return (
    role.code === "system_admin" ||
    role.code === "security_admin" ||
    role.code === "audit_admin" ||
    role.scopes.includes("*") ||
    role.scopes.some(isHighRiskScope)
  );
}

function isHighRiskScope(scope: string): boolean {
  if (["config:manage", "user:manage", "role:manage", "permission:manage"].includes(scope)) {
    return true;
  }
  return ["config:*", "user:*", "role:*", "permission:*"].includes(scope);
}
