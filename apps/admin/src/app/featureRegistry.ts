import { defineAsyncComponent, type Component } from "vue";

import type { ActiveAdminTab } from "@/app/navigation";
import type { AdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";

export interface AdminFeatureDefinition<TKey extends ActiveAdminTab = ActiveAdminTab> {
  canAccess: (capabilities: AdminCapabilityProvider) => boolean;
  component: Component;
  key: TKey;
  label: string;
}

export const ADMIN_FEATURE_REGISTRY: AdminFeatureDefinition[] = [
  {
    canAccess: (capabilities) =>
      capabilities.canReadConfig.value || capabilities.canManageConfig.value,
    component: defineAsyncComponent(() => import("@/features/config/ConfigFeature.vue")),
    key: "config",
    label: "配置管理",
  },
  {
    canAccess: (capabilities) => capabilities.canLoadDepartmentAdmin.value,
    component: defineAsyncComponent(() => import("@/features/departments/DepartmentsFeature.vue")),
    key: "departments",
    label: "部门管理",
  },
  {
    canAccess: (capabilities) => capabilities.canLoadUserAdmin.value,
    component: defineAsyncComponent(() => import("@/features/users/UsersFeature.vue")),
    key: "users",
    label: "用户管理",
  },
  {
    canAccess: (capabilities) => capabilities.canLoadImportAdmin.value,
    component: defineAsyncComponent(() => import("@/features/knowledge/KnowledgeFeature.vue")),
    key: "knowledge",
    label: "知识库管理",
  },
  {
    canAccess: (capabilities) =>
      capabilities.canLoadDiagnostics.value || capabilities.canLoadIndexOps.value,
    component: defineAsyncComponent(() => import("@/features/diagnostics/DiagnosticsFeature.vue")),
    key: "diagnostics",
    label: "查询诊断",
  },
];

export function getAdminFeatureDefinition(
  tab: ActiveAdminTab,
): AdminFeatureDefinition | null {
  return ADMIN_FEATURE_REGISTRY.find((feature) => feature.key === tab) ?? null;
}
