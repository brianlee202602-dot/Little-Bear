import type { ComputedRef, Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type { AdminDepartmentListItemData, AdminDepartmentOptionData } from "@/api/departments";

export type KnowledgeOptionSearchForm = {
  departmentKeyword: string;
  knowledgeBaseKeyword: string;
  folderKeyword: string;
};

export type KnowledgeAdminRuntimeOptions = {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  adminDepartmentOptions: Ref<AdminDepartmentOptionData[]>;
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  canImportDocuments: ComputedRef<boolean>;
  canIndexDocuments: ComputedRef<boolean>;
  canLoadImportAdmin: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canManageDocuments: ComputedRef<boolean>;
  canManageFolders: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManagePermissions: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  ensureAccessToken: () => Promise<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  optionSearchForm: KnowledgeOptionSearchForm;
  refreshDepartmentOptions: (existingAccessToken?: string) => Promise<void>;
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>;
  selectorPageSize: number;
  syncRoleBindingScopeDefault: () => void;
};
