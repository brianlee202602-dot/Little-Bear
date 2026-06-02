import type { ComputedRef, Ref } from "vue";

import type { AcceptedResponse } from "@/api/commonTypes";
import type { AdminFolderData } from "@/api/folders";
import type { ImportJobListResponse } from "@/api/imports";
import type {
  AdminKnowledgeBaseCreateRequest,
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
  AdminKnowledgeBasePatchRequest,
  AdminKnowledgeBaseResponse,
  KnowledgeBaseAccessRuleData,
  KnowledgeBasePermissionPolicyResponse,
  KnowledgeBasePermissionPutRequest,
} from "@/api/knowledgeBases";
import { useKnowledgeBaseCrudActions } from "@/features/knowledge/useKnowledgeBaseCrudActions";
import { useKnowledgeBaseIndexActions } from "@/features/knowledge/useKnowledgeBaseIndexActions";
import { useKnowledgeBaseRecordModals } from "@/features/knowledge/useKnowledgeBaseRecordModals";
import type {
  DocumentModalMode,
  KnowledgeBaseModalMode,
} from "@/features/knowledge/useKnowledgeModals";
import type { PaginationState } from "@/utils/pagination";

export interface UseKnowledgeBaseRecordsDependencies {
  adminKnowledgeBaseOptions: Ref<AdminKnowledgeBaseOptionData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  buildDepartmentKnowledgeBaseAccessRules: (departmentIds: string[]) => KnowledgeBaseAccessRuleData[];
  canCreateKnowledgeBase: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canRebuildSelectedKnowledgeBaseIndex: ComputedRef<boolean>;
  canReplaceSelectedKnowledgeBasePermissions: ComputedRef<boolean>;
  canUpdateSelectedKnowledgeBase: ComputedRef<boolean>;
  clearBatchDocumentSelection: () => void;
  clearPaginationState: (state: PaginationState) => void;
  clearSelectedDocumentDetails: () => void;
  clearSelectedDocumentMetadata: () => void;
  createAdminIndexJob: (
    payload: { kb_id: string },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  createAdminKnowledgeBase: (
    payload: AdminKnowledgeBaseCreateRequest,
    accessToken: string,
    confirmedEnterpriseVisibility: boolean,
  ) => Promise<AdminKnowledgeBaseResponse>;
  deleteAdminKnowledgeBase: (
    knowledgeBaseId: string,
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  documentManagerModalOpen: Ref<boolean>;
  documentModalMode: Ref<DocumentModalMode>;
  documentPagination: PaginationState;
  ensureAccessToken: () => Promise<string | null>;
  folderDangerForm: {
    confirmedDelete: boolean;
  };
  folderPagination: PaginationState;
  getAdminKnowledgeBase: (
    knowledgeBaseId: string,
    accessToken: string,
  ) => Promise<AdminKnowledgeBaseResponse>;
  importAdminBusy: {
    creating: boolean;
    deleting: boolean;
    rebuildingIndex: boolean;
    updating: boolean;
    updatingPermissions: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  importSearchForm: {
    kbId: string;
  };
  knowledgeBaseCreateForm: {
    accessDepartmentIds: string[];
    configScopeId: string;
    confirmedEnterpriseVisibility: boolean;
    defaultDocumentOwnerDepartmentId: string;
    defaultDocumentVisibility: "department" | "enterprise";
    kbVisibility: "enterprise" | "department_acl" | "private";
    name: string;
    ownerDepartmentId: string;
  };
  knowledgeBaseDangerForm: {
    confirmedDelete: boolean;
  };
  knowledgeBaseEditForm: {
    configScopeId: string;
    confirmedVisibilityExpand: boolean;
    defaultDocumentOwnerDepartmentId: string;
    defaultDocumentVisibility: "department" | "enterprise";
    kbVisibility: "enterprise" | "department_acl" | "private";
    name: string;
    status: "active" | "disabled" | "archived";
  };
  knowledgeBaseIndexForm: {
    confirmedRebuild: boolean;
  };
  knowledgeBaseModalMode: Ref<KnowledgeBaseModalMode>;
  knowledgeBasePermissionForm: {
    accessDepartmentIds: string[];
    confirmedReplace: boolean;
    defaultDocumentOwnerDepartmentId: string;
    defaultDocumentVisibility: "department" | "enterprise";
    kbVisibility: "enterprise" | "department_acl" | "private";
  };
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  patchAdminKnowledgeBase: (
    knowledgeBaseId: string,
    payload: AdminKnowledgeBasePatchRequest,
    accessToken: string,
    confirmedVisibilityExpand: boolean,
  ) => Promise<AdminKnowledgeBaseResponse>;
  putKnowledgeBasePermissions: (
    knowledgeBaseId: string,
    payload: KnowledgeBasePermissionPutRequest,
    accessToken: string,
    confirmed: boolean,
  ) => Promise<KnowledgeBasePermissionPolicyResponse>;
  refreshImportJobList: (accessToken: string, fallbackKbId?: string) => Promise<void>;
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>;
  refreshKnowledgeBaseAdminState: () => Promise<void>;
  refreshSelectedKnowledgeBaseDocuments: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseFolders: (existingAccessToken?: string) => Promise<void>;
  resetKnowledgeBaseCreateForm: () => void;
  selectedDocumentId: Ref<string>;
  selectedFolderId: Ref<string>;
  selectedKnowledgeBase: ComputedRef<AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
  selectedKnowledgeBaseId: Ref<string>;
  syncFolderEditForm: () => void;
  syncKnowledgeBaseEditForm: () => void;
  syncKnowledgeBasePermissionForm: () => void;
}

export function useKnowledgeBaseRecords(options: UseKnowledgeBaseRecordsDependencies) {
  const {
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    buildDepartmentKnowledgeBaseAccessRules,
    canCreateKnowledgeBase,
    canLoadIndexOps,
    canManageKnowledgeBases,
    canReadImportJobs,
    canRebuildSelectedKnowledgeBaseIndex,
    canReplaceSelectedKnowledgeBasePermissions,
    canUpdateSelectedKnowledgeBase,
    clearBatchDocumentSelection,
    clearPaginationState,
    clearSelectedDocumentDetails,
    clearSelectedDocumentMetadata,
    createAdminIndexJob,
    createAdminKnowledgeBase,
    deleteAdminKnowledgeBase,
    documentManagerModalOpen,
    documentModalMode,
    documentPagination,
    ensureAccessToken,
    folderDangerForm,
    folderPagination,
    getAdminKnowledgeBase,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    importSearchForm,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBaseIndexForm,
    knowledgeBaseModalMode,
    knowledgeBasePermissionForm,
    normalizeErrorMessage,
    patchAdminKnowledgeBase,
    putKnowledgeBasePermissions,
    refreshImportJobList,
    refreshIndexHealth,
    refreshKnowledgeBaseAdminState,
    refreshSelectedKnowledgeBaseDocuments,
    refreshSelectedKnowledgeBaseFolders,
    resetKnowledgeBaseCreateForm,
    selectedDocumentId,
    selectedFolderId,
    selectedKnowledgeBase,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
    syncFolderEditForm,
    syncKnowledgeBaseEditForm,
    syncKnowledgeBasePermissionForm,
  } = options;

  let closeKnowledgeBaseModalHandler = (): void => undefined;
  const {
    deleteSelectedKnowledgeBase,
    refreshSelectedKnowledgeBaseDetail,
    selectKnowledgeBase,
    submitCreateKnowledgeBase,
    submitKnowledgeBasePermissions,
    submitPatchKnowledgeBase,
    upsertKnowledgeBase,
  } = useKnowledgeBaseCrudActions({
    ...options,
    closeKnowledgeBaseModal: () => closeKnowledgeBaseModalHandler(),
  });

  const modalActions = useKnowledgeBaseRecordModals({
    documentManagerModalOpen,
    documentModalMode,
    importAdminFeedback,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBaseIndexForm,
    knowledgeBaseModalMode,
    knowledgeBasePermissionForm,
    resetKnowledgeBaseCreateForm,
    selectKnowledgeBase,
    syncKnowledgeBaseEditForm,
    syncKnowledgeBasePermissionForm,
  });
  closeKnowledgeBaseModalHandler = modalActions.closeKnowledgeBaseModal;
  const {
    closeKnowledgeBaseDocumentManagerModal,
    closeKnowledgeBaseModal,
    openCreateKnowledgeBaseModal,
    openDeleteKnowledgeBaseModal,
    openEditKnowledgeBaseModal,
    openKnowledgeBaseDocumentManagerModal,
    openKnowledgeBasePermissionsModal,
    openRebuildKnowledgeBaseIndexModal,
  } = modalActions;
  const { rebuildSelectedKnowledgeBaseIndex } = useKnowledgeBaseIndexActions({
    canLoadIndexOps,
    canReadImportJobs,
    canRebuildSelectedKnowledgeBaseIndex,
    closeKnowledgeBaseModal,
    createAdminIndexJob,
    ensureAccessToken,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    knowledgeBaseIndexForm,
    normalizeErrorMessage,
    refreshImportJobList,
    refreshIndexHealth,
    refreshSelectedKnowledgeBaseDocuments,
    selectedKnowledgeBase,
  });

  return {
    closeKnowledgeBaseDocumentManagerModal,
    closeKnowledgeBaseModal,
    deleteSelectedKnowledgeBase,
    openCreateKnowledgeBaseModal,
    openDeleteKnowledgeBaseModal,
    openEditKnowledgeBaseModal,
    openKnowledgeBaseDocumentManagerModal,
    openKnowledgeBasePermissionsModal,
    openRebuildKnowledgeBaseIndexModal,
    rebuildSelectedKnowledgeBaseIndex,
    refreshSelectedKnowledgeBaseDetail,
    selectKnowledgeBase,
    submitCreateKnowledgeBase,
    submitKnowledgeBasePermissions,
    submitPatchKnowledgeBase,
    upsertKnowledgeBase,
  };
}
