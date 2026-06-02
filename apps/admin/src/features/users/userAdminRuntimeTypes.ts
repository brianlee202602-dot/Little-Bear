import type { ComputedRef, Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type { AdminDepartmentOptionData } from "@/api/departments";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import type { AdminAssignableRoleOptionData, AdminRoleData } from "@/api/roles";

export type UserAdminRuntimeOptions = {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  activeKnowledgeBases: ComputedRef<AdminKnowledgeBaseOptionData[]>;
  canLoadUserAdmin: ComputedRef<boolean>;
  canManageDepartments: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManageRoles: ComputedRef<boolean>;
  canManageUsers: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadRoles: ComputedRef<boolean>;
  canReadUsers: ComputedRef<boolean>;
  clearDepartmentOptions: () => void;
  clearKnowledgeBaseOptions: () => void;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  ensureAccessToken: () => Promise<string | null>;
  isHighRiskAdminRole: (role: AdminRoleData | AdminAssignableRoleOptionData) => boolean;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  refreshDepartmentOptions: (existingAccessToken?: string) => Promise<void>;
  refreshKnowledgeBaseOptions: (existingAccessToken?: string) => Promise<void>;
  roleKeyword: () => string;
  selectorPageSize: number;
};
