import type { ComputedRef, Ref } from "vue";

import type { AcceptedResponse } from "@/api/commonTypes";
import type {
  AdminDocumentData,
  AdminDocumentListResponse,
  AdminDocumentResponse,
  AdminDocumentListItemData,
  ChunkData,
  ChunkListResponse,
  DocumentVersionData,
  DocumentVersionListResponse,
  IndexVersionData,
  IndexVersionListResponse,
  PermissionPolicyResponse,
} from "@/api/documents";
import type { AdminKnowledgeBaseData, AdminKnowledgeBaseListItemData } from "@/api/knowledgeBases";
import type { DocumentModalMode } from "@/features/knowledge/useKnowledgeModals";
import { useKnowledgeDocumentLoaders } from "@/features/knowledge/useKnowledgeDocumentLoaders";
import { useKnowledgeDocumentIndexActions } from "@/features/knowledge/useKnowledgeDocumentIndexActions";
import type { PaginationState } from "@/utils/pagination";

export interface UseKnowledgeDocumentsDependencies {
  adminDocuments: Ref<AdminDocumentListItemData[]>;
  canCleanupSelectedIndexVersions: ComputedRef<boolean>;
  canIndexDocuments: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canManageDocuments: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canRebuildSelectedDocumentIndex: ComputedRef<boolean>;
  canRebuildSelectedDocumentsIndex: ComputedRef<boolean>;
  canReplaceSelectedDocumentPermissions: ComputedRef<boolean>;
  clearBatchDocumentSelection: () => void;
  clearIndexVersionCleanupSelection: () => void;
  clearPaginationState: (state: PaginationState) => void;
  clearSelectedDocumentDetails: () => void;
  createAdminDocumentIndexJob: (
    documentId: string,
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  createAdminIndexJob: (
    payload: { document_ids: string[] },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  createAdminIndexVersionCleanupJob: (
    payload: { index_version_ids: string[] },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  documentChunkPagination: PaginationState;
  documentIndexForm: {
    confirmedRebuild: boolean;
  };
  documentIndexVersionPagination: PaginationState;
  documentModalMode: Ref<DocumentModalMode>;
  documentPagination: PaginationState;
  documentPermissionForm: {
    confirmedReplace: boolean;
    ownerDepartmentId: string;
    visibility: "department" | "enterprise";
  };
  documentPermissionParentConflict: ComputedRef<string>;
  documentSearchForm: {
    status: string;
  };
  documentVersionPagination: PaginationState;
  ensureAccessToken: () => Promise<string | null>;
  getAdminDocument: (documentId: string, accessToken: string) => Promise<AdminDocumentResponse>;
  highlightedDocumentChunkId: Ref<string>;
  importAdminBusy: {
    cleaningIndexVersions: boolean;
    loadingDocumentDetails: boolean;
    loadingDocuments: boolean;
    loadingDocumentVersions: boolean;
    loadingIndexVersions: boolean;
    rebuildingBatchIndex: boolean;
    rebuildingIndex: boolean;
    updatingPermissions: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  listAdminDocumentChunks: (
    documentId: string,
    accessToken: string,
    filters: { page?: number; page_size?: number },
  ) => Promise<ChunkListResponse>;
  listAdminDocumentIndexVersions: (
    documentId: string,
    accessToken: string,
    filters: { page?: number; page_size?: number },
  ) => Promise<IndexVersionListResponse>;
  listAdminDocuments: (
    knowledgeBaseId: string,
    accessToken: string,
    filters: { page?: number; page_size?: number; status?: string },
  ) => Promise<AdminDocumentListResponse>;
  listAdminDocumentVersions: (
    documentId: string,
    accessToken: string,
    filters: { page?: number; page_size?: number },
  ) => Promise<DocumentVersionListResponse>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  paginationTotalPages: (state: PaginationState) => number;
  pruneSelectedBatchDocuments: () => void;
  pruneSelectedIndexVersionsForCleanup: () => void;
  putDocumentPermissions: (
    documentId: string,
    payload: {
      owner_department_id?: string | null;
      visibility: "department" | "enterprise";
    },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<PermissionPolicyResponse>;
  refreshImportJobList: (accessToken: string, fallbackKbId?: string) => Promise<void>;
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>;
  selectedAdminDocument: ComputedRef<AdminDocumentData | AdminDocumentListItemData | null>;
  selectedAdminDocumentDetail: Ref<AdminDocumentData | null>;
  selectedBatchRebuildDocumentIds: ComputedRef<string[]>;
  selectedCleanupPendingDeleteIndexVersionIds: ComputedRef<string[]>;
  selectedDocumentChunks: Ref<ChunkData[]>;
  selectedDocumentId: Ref<string>;
  selectedDocumentIndexVersions: Ref<IndexVersionData[]>;
  selectedDocumentVersions: Ref<DocumentVersionData[]>;
  selectedKnowledgeBase: ComputedRef<AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null>;
  syncDocumentPermissionForm: () => void;
  syncPaginationState: (
    state: PaginationState,
    pagination: { page: number; page_size: number; total: number },
  ) => void;
}

export function useKnowledgeDocuments(options: UseKnowledgeDocumentsDependencies) {
  const {
    adminDocuments,
    canCleanupSelectedIndexVersions,
    canIndexDocuments,
    canLoadIndexOps,
    canManageDocuments,
    canReadImportJobs,
    canRebuildSelectedDocumentIndex,
    canRebuildSelectedDocumentsIndex,
    canReplaceSelectedDocumentPermissions,
    clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection,
    clearPaginationState,
    clearSelectedDocumentDetails,
    createAdminDocumentIndexJob,
    createAdminIndexJob,
    createAdminIndexVersionCleanupJob,
    documentChunkPagination,
    documentIndexForm,
    documentIndexVersionPagination,
    documentModalMode,
    documentPagination,
    documentPermissionForm,
    documentPermissionParentConflict,
    documentSearchForm,
    documentVersionPagination,
    ensureAccessToken,
    getAdminDocument,
    highlightedDocumentChunkId,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    listAdminDocumentChunks,
    listAdminDocumentIndexVersions,
    listAdminDocuments,
    listAdminDocumentVersions,
    normalizeErrorMessage,
    paginationTotalPages,
    putDocumentPermissions,
    pruneSelectedBatchDocuments,
    pruneSelectedIndexVersionsForCleanup,
    refreshImportJobList,
    refreshIndexHealth,
    selectedAdminDocument,
    selectedAdminDocumentDetail,
    selectedBatchRebuildDocumentIds,
    selectedCleanupPendingDeleteIndexVersionIds,
    selectedDocumentChunks,
    selectedDocumentId,
    selectedDocumentIndexVersions,
    selectedDocumentVersions,
    selectedKnowledgeBase,
    syncDocumentPermissionForm,
    syncPaginationState,
  } = options;

  const {
    clearSelectedDocumentMetadata,
    closeDocumentModal,
    openDocumentDetailsModal,
    openDocumentPermissionsModal,
    refreshSelectedDocumentDetails,
    refreshSelectedDocumentIndexVersions,
    refreshSelectedDocumentMetadata,
    refreshSelectedDocumentVersions,
    refreshSelectedKnowledgeBaseDocuments,
  } = useKnowledgeDocumentLoaders(options);

  async function submitDocumentPermissions(): Promise<void> {
    const document = selectedAdminDocument.value;
    if (documentPermissionParentConflict.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: documentPermissionParentConflict.value,
      };
      return;
    }
    if (!document || !canReplaceSelectedDocumentPermissions.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请选择文档、填写所属部门并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.updatingPermissions = true;
    try {
      await putDocumentPermissions(
        document.id,
        {
          visibility: documentPermissionForm.visibility,
          owner_department_id: documentPermissionForm.ownerDepartmentId.trim(),
        },
        accessToken,
        true,
      );
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
      importAdminFeedback.value = {
        tone: "success",
        message: "文档权限策略已更新。",
      };
      closeDocumentModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "更新文档权限失败"),
      };
    } finally {
      importAdminBusy.updatingPermissions = false;
    }
  }

  const {
    cleanupSelectedIndexVersions,
    rebuildSelectedDocumentIndex,
    rebuildSelectedDocumentsIndex,
  } = useKnowledgeDocumentIndexActions({
    canCleanupSelectedIndexVersions,
    canLoadIndexOps,
    canReadImportJobs,
    canRebuildSelectedDocumentIndex,
    canRebuildSelectedDocumentsIndex,
    clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection,
    createAdminDocumentIndexJob,
    createAdminIndexJob,
    createAdminIndexVersionCleanupJob,
    documentIndexForm,
    ensureAccessToken,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    normalizeErrorMessage,
    refreshImportJobList,
    refreshIndexHealth,
    refreshSelectedDocumentIndexVersions,
    refreshSelectedKnowledgeBaseDocuments,
    selectedAdminDocument,
    selectedBatchRebuildDocumentIds,
    selectedCleanupPendingDeleteIndexVersionIds,
    selectedKnowledgeBase,
  });

  return {
    cleanupSelectedIndexVersions,
    clearSelectedDocumentMetadata,
    closeDocumentModal,
    openDocumentDetailsModal,
    openDocumentPermissionsModal,
    rebuildSelectedDocumentIndex,
    rebuildSelectedDocumentsIndex,
    refreshSelectedDocumentDetails,
    refreshSelectedDocumentIndexVersions,
    refreshSelectedDocumentMetadata,
    refreshSelectedDocumentVersions,
    refreshSelectedKnowledgeBaseDocuments,
    submitDocumentPermissions,
  };
}
