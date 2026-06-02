export const builtinRoleLabels: Record<string, string> = {
  system_admin: "系统管理员",
  security_admin: "安全管理员",
  audit_admin: "审计管理员",
  department_admin: "部门管理员",
  knowledge_base_admin: "知识库管理员",
  employee: "普通员工",
};

export function formatRoleLabel(
  role: { code?: string | null; name?: string | null } | null | undefined,
): string {
  if (!role) {
    return "-";
  }
  const code = role.code?.trim();
  if (code && builtinRoleLabels[code]) {
    return builtinRoleLabels[code];
  }
  return role.name?.trim() || code || "-";
}

export function formatRoleCodeLabel(roleCode: string | null | undefined, fallback = "-"): string {
  if (!roleCode) {
    return fallback;
  }
  return builtinRoleLabels[roleCode] ?? roleCode;
}

export function formatRoleList(
  roles: Array<{ code?: string | null; name?: string | null }>,
): string {
  const labels = roles.map((role) => formatRoleLabel(role)).filter((label) => label !== "-");
  return labels.length ? labels.join(" / ") : "-";
}
