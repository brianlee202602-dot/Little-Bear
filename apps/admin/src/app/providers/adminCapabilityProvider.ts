import { inject, provide, type ComputedRef, type InjectionKey } from "vue";

import type { ActiveAdminTab, AdminTabDefinition } from "@/app/navigation";

export interface AdminCapabilityProvider {
  adminTabDefinitions: AdminTabDefinition[];
  canAccessAdminPortal: () => boolean;
  canAccessAdminTab: (tab: ActiveAdminTab) => boolean;
  canImportDocuments: ComputedRef<boolean>;
  canIndexDocuments: ComputedRef<boolean>;
  canLoadDepartmentAdmin: ComputedRef<boolean>;
  canLoadDiagnostics: ComputedRef<boolean>;
  canLoadImportAdmin: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canLoadUserAdmin: ComputedRef<boolean>;
  canManageConfig: ComputedRef<boolean>;
  canManageDepartments: ComputedRef<boolean>;
  canManageDocuments: ComputedRef<boolean>;
  canManageFolders: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManagePermissions: ComputedRef<boolean>;
  canManageRoles: ComputedRef<boolean>;
  canManageUsers: ComputedRef<boolean>;
  canReadAudit: ComputedRef<boolean>;
  canReadConfig: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canReadRoles: ComputedRef<boolean>;
  canReadUsers: ComputedRef<boolean>;
  visibleAdminTabs: ComputedRef<AdminTabDefinition[]>;
}

const ADMIN_CAPABILITY_PROVIDER_KEY: InjectionKey<AdminCapabilityProvider> =
  Symbol("AdminCapabilityProvider");

export function provideAdminCapabilities(provider: AdminCapabilityProvider): void {
  provide(ADMIN_CAPABILITY_PROVIDER_KEY, provider);
}

export function useAdminCapabilityProvider(): AdminCapabilityProvider {
  const provider = inject(ADMIN_CAPABILITY_PROVIDER_KEY);
  if (!provider) {
    throw new Error("ADMIN_CAPABILITY_PROVIDER_MISSING");
  }
  return provider;
}
