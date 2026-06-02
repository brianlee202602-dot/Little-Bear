import {
  createAdminDocumentIndexJob,
  getAdminDocument,
  listAdminDocumentChunks,
  listAdminDocumentIndexVersions,
  listAdminDocuments,
  listAdminDocumentVersions,
  putDocumentPermissions,
} from "@/api/documents";
import {
  createAdminFolder,
  deleteAdminFolder,
  listAdminFolderOptions,
  listAdminFolders,
  patchAdminFolder,
} from "@/api/folders";
import { listAdminImportJobs, uploadKnowledgeBaseDocuments } from "@/api/imports";
import {
  createAdminIndexJob,
  createAdminIndexVersionCleanupJob,
  retryAdminIndexJobs,
} from "@/api/indexOps";
import {
  createAdminKnowledgeBase,
  deleteAdminKnowledgeBase,
  getAdminKnowledgeBase,
  listAdminKnowledgeBaseOptions,
  listAdminKnowledgeBases,
  patchAdminKnowledgeBase,
  putKnowledgeBasePermissions,
} from "@/api/knowledgeBases";
import { importJobListItemFromDetail } from "@/features/knowledge/knowledgeDisplay";
import type { KnowledgeAdminRuntimeOptions } from "@/features/knowledge/knowledgeAdminRuntimeTypes";
import type { useDocumentSelection } from "@/features/knowledge/useDocumentSelection";
import type { useKnowledgeAdminState } from "@/features/knowledge/useKnowledgeAdminState";
import { useKnowledgeBaseAdmin } from "@/features/knowledge/useKnowledgeBaseAdmin";
import type { useKnowledgeDerivedState } from "@/features/knowledge/useKnowledgeDerivedState";
import type { useKnowledgeDocumentIndexState } from "@/features/knowledge/useKnowledgeDocumentIndexState";
import type { useKnowledgeFailedIndexJobs } from "@/features/knowledge/useKnowledgeFailedIndexJobs";
import type { useKnowledgePermissions } from "@/features/knowledge/useKnowledgePermissions";
import { uniqueById } from "@/utils/collections";
import {
  clearPaginationState,
  paginationTotalPages,
  syncPaginationState,
} from "@/utils/pagination";

interface UseKnowledgeAdminActionsOptions {
  documentIndexState: ReturnType<typeof useKnowledgeDocumentIndexState>;
  documentSelection: ReturnType<typeof useDocumentSelection>;
  failedIndexJobState: ReturnType<typeof useKnowledgeFailedIndexJobs>;
  knowledgeAdminState: ReturnType<typeof useKnowledgeAdminState>;
  knowledgeDerivedState: ReturnType<typeof useKnowledgeDerivedState>;
  knowledgePermissionState: ReturnType<typeof useKnowledgePermissions>;
  runtimeOptions: KnowledgeAdminRuntimeOptions;
}

export function useKnowledgeAdminActions(options: UseKnowledgeAdminActionsOptions) {
  const {
    documentIndexState,
    documentSelection,
    failedIndexJobState,
    knowledgeAdminState,
    knowledgeDerivedState,
    knowledgePermissionState,
    runtimeOptions,
  } = options;

  return useKnowledgeBaseAdmin({
    activeFolders: knowledgeDerivedState.activeFolders,
    activeKnowledgeBases: knowledgeDerivedState.activeKnowledgeBases,
    adminDepartmentOptions: runtimeOptions.adminDepartmentOptions,
    adminDocuments: knowledgeAdminState.adminDocuments,
    adminFolders: knowledgeAdminState.adminFolders,
    adminFolderOptions: knowledgeAdminState.adminFolderOptions,
    adminImportJobs: knowledgeAdminState.adminImportJobs,
    adminKnowledgeBaseOptions: knowledgeAdminState.adminKnowledgeBaseOptions,
    adminKnowledgeBases: knowledgeAdminState.adminKnowledgeBases,
    buildDepartmentKnowledgeBaseAccessRules:
      knowledgePermissionState.buildDepartmentKnowledgeBaseAccessRules,
    canCleanupSelectedIndexVersions: documentIndexState.canCleanupSelectedIndexVersions,
    canCreateFolder: knowledgePermissionState.canCreateFolder,
    canCreateKnowledgeBase: knowledgePermissionState.canCreateKnowledgeBase,
    canImportDocuments: runtimeOptions.canImportDocuments,
    canIndexDocuments: runtimeOptions.canIndexDocuments,
    canLoadImportAdmin: runtimeOptions.canLoadImportAdmin,
    canLoadIndexOps: runtimeOptions.canLoadIndexOps,
    canManageDocuments: runtimeOptions.canManageDocuments,
    canManageFolders: runtimeOptions.canManageFolders,
    canManageKnowledgeBases: runtimeOptions.canManageKnowledgeBases,
    canReadDepartments: runtimeOptions.canReadDepartments,
    canReadImportJobs: runtimeOptions.canReadImportJobs,
    canRebuildSelectedDocumentIndex: documentIndexState.canRebuildSelectedDocumentIndex,
    canRebuildSelectedDocumentsIndex: documentIndexState.canRebuildSelectedDocumentsIndex,
    canRebuildSelectedKnowledgeBaseIndex:
      knowledgePermissionState.canRebuildSelectedKnowledgeBaseIndex,
    canReplaceSelectedDocumentPermissions:
      knowledgePermissionState.canReplaceSelectedDocumentPermissions,
    canReplaceSelectedKnowledgeBasePermissions:
      knowledgePermissionState.canReplaceSelectedKnowledgeBasePermissions,
    canRetrySelectedFailedIndexJobs: failedIndexJobState.canRetrySelectedFailedIndexJobs,
    canUpdateSelectedFolder: knowledgePermissionState.canUpdateSelectedFolder,
    canUpdateSelectedKnowledgeBase: knowledgePermissionState.canUpdateSelectedKnowledgeBase,
    canUploadImportFiles: knowledgePermissionState.canUploadImportFiles,
    clearBatchDocumentSelection: documentSelection.clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection: documentSelection.clearIndexVersionCleanupSelection,
    clearPaginationState,
    clearSelectedDocumentDetails: documentSelection.clearSelectedDocumentDetails,
    createAdminDocumentIndexJob,
    createAdminFolder,
    createAdminIndexJob,
    createAdminIndexVersionCleanupJob,
    createAdminKnowledgeBase,
    deleteAdminFolder,
    deleteAdminKnowledgeBase,
    documentChunkPagination: knowledgeAdminState.documentChunkPagination,
    documentIndexForm: knowledgeAdminState.documentIndexForm,
    documentIndexVersionPagination: knowledgeAdminState.documentIndexVersionPagination,
    documentManagerModalOpen: knowledgeAdminState.documentManagerModalOpen,
    documentModalMode: knowledgeAdminState.documentModalMode,
    documentPagination: knowledgeAdminState.documentPagination,
    documentPermissionForm: knowledgeAdminState.documentPermissionForm,
    documentPermissionParentConflict:
      knowledgePermissionState.documentPermissionParentConflict,
    documentSearchForm: knowledgeAdminState.documentSearchForm,
    documentVersionPagination: knowledgeAdminState.documentVersionPagination,
    ensureAccessToken: runtimeOptions.ensureAccessToken,
    failedIndexJobPagination: knowledgeAdminState.failedIndexJobPagination,
    failedIndexJobs: knowledgeAdminState.failedIndexJobs,
    folderCreateForm: knowledgeAdminState.folderCreateForm,
    folderDangerForm: knowledgeAdminState.folderDangerForm,
    folderEditForm: knowledgeAdminState.folderEditForm,
    folderModalMode: knowledgeAdminState.folderModalMode,
    folderPagination: knowledgeAdminState.folderPagination,
    getAdminDocument,
    getAdminKnowledgeBase,
    highlightedDocumentChunkId: documentSelection.highlightedDocumentChunkId,
    importAdminBusy: knowledgeAdminState.importAdminBusy,
    importAdminFeedback: knowledgeAdminState.importAdminFeedback,
    importFileInputKey: knowledgeAdminState.importFileInputKey,
    importJobListItemFromDetail,
    importJobPagination: knowledgeAdminState.importJobPagination,
    importSearchForm: knowledgeAdminState.importSearchForm,
    importUploadForm: knowledgeAdminState.importUploadForm,
    importUploadPermissionParentConflict:
      knowledgePermissionState.importUploadPermissionParentConflict,
    indexRetryForm: knowledgeAdminState.indexRetryForm,
    knowledgeBaseCreateForm: knowledgeAdminState.knowledgeBaseCreateForm,
    knowledgeBaseDangerForm: knowledgeAdminState.knowledgeBaseDangerForm,
    knowledgeBaseEditForm: knowledgeAdminState.knowledgeBaseEditForm,
    knowledgeBaseIndexForm: knowledgeAdminState.knowledgeBaseIndexForm,
    knowledgeBaseModalMode: knowledgeAdminState.knowledgeBaseModalMode,
    knowledgeBasePagination: knowledgeAdminState.knowledgeBasePagination,
    knowledgeBasePermissionForm: knowledgeAdminState.knowledgeBasePermissionForm,
    knowledgeBaseSearchForm: knowledgeAdminState.knowledgeBaseSearchForm,
    listAdminDocumentChunks,
    listAdminDocumentIndexVersions,
    listAdminDocuments,
    listAdminDocumentVersions,
    listAdminFolderOptions,
    listAdminFolders,
    listAdminImportJobs,
    listAdminKnowledgeBaseOptions,
    listAdminKnowledgeBases,
    normalizeErrorMessage: runtimeOptions.normalizeErrorMessage,
    onAllBatchDocumentsToggle: documentSelection.onAllBatchDocumentsToggle,
    onAllIndexVersionsForCleanupToggle:
      documentSelection.onAllIndexVersionsForCleanupToggle,
    onBatchDocumentSelectionToggle: documentSelection.onBatchDocumentSelectionToggle,
    onIndexVersionCleanupSelectionToggle:
      documentSelection.onIndexVersionCleanupSelectionToggle,
    optionSearchForm: runtimeOptions.optionSearchForm,
    paginationTotalPages,
    patchAdminFolder,
    patchAdminKnowledgeBase,
    pruneSelectedBatchDocuments: documentSelection.pruneSelectedBatchDocuments,
    pruneSelectedIndexVersionsForCleanup:
      documentSelection.pruneSelectedIndexVersionsForCleanup,
    putDocumentPermissions,
    putKnowledgeBasePermissions,
    refreshDepartmentOptions: runtimeOptions.refreshDepartmentOptions,
    refreshIndexHealth: runtimeOptions.refreshIndexHealth,
    resetKnowledgeBaseCreateForm: knowledgePermissionState.resetKnowledgeBaseCreateForm,
    retryAdminIndexJobs,
    selectedAdminDocument: knowledgeDerivedState.selectedAdminDocument,
    selectedAdminDocumentDetail: documentSelection.selectedAdminDocumentDetail,
    selectedBatchRebuildDocumentIds: documentSelection.selectedBatchRebuildDocumentIds,
    selectedCleanupPendingDeleteIndexVersionIds:
      documentSelection.selectedCleanupPendingDeleteIndexVersionIds,
    selectedDocumentChunks: documentSelection.selectedDocumentChunks,
    selectedDocumentId: knowledgeAdminState.selectedDocumentId,
    selectedDocumentIndexVersions: documentSelection.selectedDocumentIndexVersions,
    selectedDocumentVersions: documentSelection.selectedDocumentVersions,
    selectedFailedIndexJobIds: knowledgeAdminState.selectedFailedIndexJobIds,
    selectedFolder: knowledgeDerivedState.selectedFolder,
    selectedFolderId: knowledgeAdminState.selectedFolderId,
    selectedImportFiles: knowledgeAdminState.selectedImportFiles,
    selectedImportKnowledgeBase: knowledgeDerivedState.selectedImportKnowledgeBase,
    selectedKnowledgeBase: knowledgeDerivedState.selectedKnowledgeBase,
    selectedKnowledgeBaseDetail: knowledgeAdminState.selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId: knowledgeAdminState.selectedKnowledgeBaseId,
    selectorPageSize: runtimeOptions.selectorPageSize,
    syncDocumentPermissionForm: knowledgePermissionState.syncDocumentPermissionForm,
    syncFolderEditForm: knowledgePermissionState.syncFolderEditForm,
    syncKnowledgeBaseEditForm: knowledgePermissionState.syncKnowledgeBaseEditForm,
    syncKnowledgeBasePermissionForm: knowledgePermissionState.syncKnowledgeBasePermissionForm,
    syncPaginationState,
    syncRoleBindingScopeDefault: runtimeOptions.syncRoleBindingScopeDefault,
    uniqueById,
    uploadKnowledgeBaseDocuments,
  });
}
