import { computed, type Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import {
  ADMIN_TAB_DEFINITIONS,
  canAccessAdminTab as canAccessAdminTabByFlags,
  hasScope,
  type ActiveAdminTab,
  type AdminTabDefinition,
} from "@/app/navigation";

export function useAdminCapabilities(
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>,
) {
  const scopes = computed(() => currentUser.value?.scopes ?? []);

  const canManageConfig = computed(() => hasScope(scopes.value, "config:manage"));
  const canReadConfig = computed(() => hasScope(scopes.value, "config:read"));
  const canReadAudit = computed(() => hasScope(scopes.value, "audit:read"));
  const canLoadDiagnostics = computed(() => canReadAudit.value);

  const canManageUsers = computed(() => hasScope(scopes.value, "user:manage"));
  const canReadUsers = computed(() => hasScope(scopes.value, "user:read") || canManageUsers.value);

  const canManageDepartments = computed(() => hasScope(scopes.value, "org:manage"));
  const canReadDepartments = computed(
    () => hasScope(scopes.value, "org:read") || canManageDepartments.value,
  );

  const canManageRoles = computed(() => hasScope(scopes.value, "role:manage"));
  const canReadRoles = computed(() => hasScope(scopes.value, "role:read") || canManageRoles.value);

  const canManageKnowledgeBases = computed(() =>
    hasScope(scopes.value, "knowledge_base:manage"),
  );
  const canManageDocuments = computed(() => hasScope(scopes.value, "document:manage"));
  const canIndexDocuments = computed(() => hasScope(scopes.value, "document:index"));
  const canLoadIndexOps = computed(() => canIndexDocuments.value);
  const canManageFolders = computed(() => hasScope(scopes.value, "folder:manage"));
  const canImportDocuments = computed(() => hasScope(scopes.value, "document:import"));
  const canManagePermissions = computed(() => hasScope(scopes.value, "permission:manage"));
  const canReadImportJobs = computed(() => hasScope(scopes.value, "import_job:read"));

  const canLoadImportAdmin = computed(
    () =>
      canImportDocuments.value ||
      canReadImportJobs.value ||
      canManageKnowledgeBases.value ||
      canManageFolders.value ||
      canManageDocuments.value ||
      canIndexDocuments.value ||
      canManagePermissions.value,
  );
  const canLoadUserAdmin = computed(() => canReadUsers.value || canReadRoles.value);
  const canLoadDepartmentAdmin = computed(
    () => canReadDepartments.value || canManageDepartments.value,
  );

  const adminTabDefinitions: AdminTabDefinition[] = ADMIN_TAB_DEFINITIONS;

  function canAccessAdminTab(tab: ActiveAdminTab): boolean {
    return canAccessAdminTabByFlags(tab, {
      canReadConfig: canReadConfig.value,
      canManageConfig: canManageConfig.value,
      canLoadDepartmentAdmin: canLoadDepartmentAdmin.value,
      canLoadUserAdmin: canLoadUserAdmin.value,
      canLoadImportAdmin: canLoadImportAdmin.value,
      canLoadDiagnostics: canLoadDiagnostics.value,
      canLoadIndexOps: canLoadIndexOps.value,
    });
  }

  const visibleAdminTabs = computed(() =>
    adminTabDefinitions.filter((item) => canAccessAdminTab(item.key)),
  );

  function canAccessAdminPortal(): boolean {
    return adminTabDefinitions.some((item) => canAccessAdminTab(item.key));
  }

  return {
    adminTabDefinitions,
    canAccessAdminPortal,
    canAccessAdminTab,
    canImportDocuments,
    canIndexDocuments,
    canLoadDepartmentAdmin,
    canLoadDiagnostics,
    canLoadImportAdmin,
    canLoadIndexOps,
    canLoadUserAdmin,
    canManageConfig,
    canManageDepartments,
    canManageDocuments,
    canManageFolders,
    canManageKnowledgeBases,
    canManagePermissions,
    canManageRoles,
    canManageUsers,
    canReadAudit,
    canReadConfig,
    canReadDepartments,
    canReadImportJobs,
    canReadRoles,
    canReadUsers,
    visibleAdminTabs,
  };
}
