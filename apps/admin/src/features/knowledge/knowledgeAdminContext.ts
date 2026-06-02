import type { ComputedRef, Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type {
  AdminDepartmentListItemData,
  AdminDepartmentOptionData,
} from "@/api/departments";
import type { AdminKnowledgeBaseListItemData } from "@/api/knowledgeBases";
import type { useKnowledgeDisplayLookups } from "@/features/knowledge/knowledgeDisplayLookups";
import type * as KnowledgeDisplay from "@/features/knowledge/knowledgeDisplay";
import type { useKnowledgeAdminRuntime } from "@/features/knowledge/useKnowledgeAdminRuntime";
import type * as DateUtils from "@/utils/date";
import type * as DisplayUtils from "@/utils/display";
import type * as PaginationUtils from "@/utils/pagination";

type KnowledgeRuntime = ReturnType<typeof useKnowledgeAdminRuntime>;
type KnowledgeDisplayLookups = ReturnType<typeof useKnowledgeDisplayLookups>;

type OptionSearchForm = {
  departmentKeyword: string;
  folderKeyword: string;
  knowledgeBaseKeyword: string;
};

type KnowledgeFeatureBindings = {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  authenticated: ComputedRef<boolean>;
  canImportDocuments: ComputedRef<boolean>;
  canIndexDocuments: ComputedRef<boolean>;
  canLoadImportAdmin: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canManageDepartments: ComputedRef<boolean>;
  canManageDocuments: ComputedRef<boolean>;
  canManageFolders: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManagePermissions: ComputedRef<boolean>;
  canReadDepartments: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  changePaginationPage: (
    state: PaginationUtils.PaginationState,
    refresh: () => Promise<void>,
    page: number,
  ) => void;
  changePaginationPageSize: (
    state: PaginationUtils.PaginationState,
    refresh: () => Promise<void>,
    pageSize?: number,
  ) => void;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  documentIndexStatusTone: typeof KnowledgeDisplay.documentIndexStatusTone;
  documentLifecycleStatusTone: typeof KnowledgeDisplay.documentLifecycleStatusTone;
  documentVersionStatusTone: typeof KnowledgeDisplay.documentVersionStatusTone;
  documentVisibilityLabel: typeof KnowledgeDisplay.documentVisibilityLabel;
  folderStatusTone: typeof KnowledgeDisplay.folderStatusTone;
  formatAuditTime: typeof DateUtils.formatAuditTime;
  formatChunkPageRange: typeof KnowledgeDisplay.formatChunkPageRange;
  formatDepartmentLabel: (
    department: { code?: string | null; name?: string | null } | null | undefined,
  ) => string;
  formatDepartmentList: (
    departments: Array<{ code?: string | null; name?: string | null }>,
  ) => string;
  formatDocumentCount: typeof KnowledgeDisplay.formatDocumentCount;
  formatDocumentVersion: typeof KnowledgeDisplay.formatDocumentVersion;
  formatFileSize: typeof KnowledgeDisplay.formatFileSize;
  formatFolderLabel: typeof KnowledgeDisplay.formatFolderLabel;
  formatImportJobTitle: typeof KnowledgeDisplay.formatImportJobTitle;
  formatKnowledgeBaseLabel: typeof KnowledgeDisplay.formatKnowledgeBaseLabel;
  formatStatusOption: typeof DisplayUtils.formatStatusOption;
  formatStatusText: typeof DisplayUtils.formatStatusText;
  importJobStageLabel: typeof KnowledgeDisplay.importJobStageLabel;
  importJobStatusTone: typeof KnowledgeDisplay.importJobStatusTone;
  indexVersionStatusTone: typeof KnowledgeDisplay.indexVersionStatusTone;
  knowledgeBaseStatusTone: typeof KnowledgeDisplay.knowledgeBaseStatusTone;
  knowledgeBaseVisibilityLabel: typeof KnowledgeDisplay.knowledgeBaseVisibilityLabel;
  optionSearchForm: OptionSearchForm;
  pageSizeOptions: number[];
  paginationEnd: typeof PaginationUtils.paginationEnd;
  paginationStart: typeof PaginationUtils.paginationStart;
  refreshDepartmentOptionsFromSearch: () => void;
  refreshFirstPage: typeof PaginationUtils.refreshFirstPage;
  toneClass: typeof DisplayUtils.toneClass;
  userRoleLabels: ComputedRef<string>;
};

export type KnowledgeBaseAdminContext = KnowledgeRuntime &
  KnowledgeDisplayLookups &
  KnowledgeFeatureBindings;

export function createKnowledgeAdminContext(
  options: KnowledgeBaseAdminContext,
): KnowledgeBaseAdminContext {
  return options;
}
