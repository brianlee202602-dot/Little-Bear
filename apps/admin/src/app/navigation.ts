export type ActiveAdminTab = "config" | "departments" | "users" | "knowledge" | "diagnostics";

export type AdminTabDefinition = {
  key: ActiveAdminTab;
  label: string;
};

export type AdminTabAccessFlags = {
  canReadConfig: boolean;
  canManageConfig: boolean;
  canLoadDepartmentAdmin: boolean;
  canLoadUserAdmin: boolean;
  canLoadImportAdmin: boolean;
  canLoadDiagnostics: boolean;
  canLoadIndexOps: boolean;
};

export const ADMIN_TAB_DEFINITIONS: AdminTabDefinition[] = [
  { key: "config", label: "配置管理" },
  { key: "departments", label: "部门管理" },
  { key: "users", label: "用户管理" },
  { key: "knowledge", label: "知识库管理" },
  { key: "diagnostics", label: "查询诊断" },
];

export function canAccessAdminTab(tab: ActiveAdminTab, flags: AdminTabAccessFlags): boolean {
  if (tab === "config") {
    return flags.canReadConfig || flags.canManageConfig;
  }
  if (tab === "departments") {
    return flags.canLoadDepartmentAdmin;
  }
  if (tab === "users") {
    return flags.canLoadUserAdmin;
  }
  if (tab === "knowledge") {
    return flags.canLoadImportAdmin;
  }
  if (tab === "diagnostics") {
    return flags.canLoadDiagnostics || flags.canLoadIndexOps;
  }
  return false;
}

export function hasScope(scopes: string[], requiredScope: string): boolean {
  if (scopes.includes("*") || scopes.includes(requiredScope)) {
    return true;
  }
  const prefix = requiredScope.split(":", 1)[0];
  return scopes.includes(`${prefix}:*`);
}
