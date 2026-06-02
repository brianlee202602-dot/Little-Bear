import { createKnowledgeDepartmentFormatter } from "@/features/knowledge/knowledgeDepartmentLookup";
import type { KnowledgeAdminRuntimeOptions } from "@/features/knowledge/knowledgeAdminRuntimeTypes";
import { useKnowledgeAdminState } from "@/features/knowledge/useKnowledgeAdminState";
import { useKnowledgeDerivedState } from "@/features/knowledge/useKnowledgeDerivedState";
import {
  isDocumentBatchRebuildEligible,
  useKnowledgeDocumentIndexState,
} from "@/features/knowledge/useKnowledgeDocumentIndexState";
import { useDocumentSelection } from "@/features/knowledge/useDocumentSelection";
import { useKnowledgeFailedIndexJobs } from "@/features/knowledge/useKnowledgeFailedIndexJobs";
import { useKnowledgePermissions } from "@/features/knowledge/useKnowledgePermissions";
import { clearPaginationState } from "@/utils/pagination";

type UseKnowledgeRuntimeSlicesOptions = {
  knowledgeAdminState: ReturnType<typeof useKnowledgeAdminState>;
  runtimeOptions: KnowledgeAdminRuntimeOptions;
};

export function useKnowledgeRuntimeSlices(options: UseKnowledgeRuntimeSlicesOptions) {
  const { knowledgeAdminState, runtimeOptions } = options;
  const {
    adminDocuments,
    adminFolderOptions,
    adminFolders,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    documentChunkPagination,
    documentIndexForm,
    documentIndexVersionPagination,
    documentPermissionForm,
    documentVersionPagination,
    failedIndexJobs,
    folderCreateForm,
    folderDangerForm,
    folderEditForm,
    importAdminBusy,
    importUploadForm,
    indexRetryForm,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBaseIndexForm,
    knowledgeBasePermissionForm,
    selectedDocumentId,
    selectedFailedIndexJobIds,
    selectedFolderId,
    selectedImportFiles,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
  } = knowledgeAdminState;

  const documentSelection = useDocumentSelection({
    adminDocuments,
    clearPaginationState,
    documentChunkPagination,
    documentIndexForm,
    documentIndexVersionPagination,
    documentVersionPagination,
    isDocumentBatchRebuildEligible,
  });
  const formatDepartmentById = createKnowledgeDepartmentFormatter({
    adminDepartmentOptions: runtimeOptions.adminDepartmentOptions,
    adminDepartments: runtimeOptions.adminDepartments,
    adminKnowledgeBases,
    currentUser: runtimeOptions.currentUser,
    selectedKnowledgeBaseDetail,
  });
  const knowledgeDerivedState = useKnowledgeDerivedState({
    adminDocuments,
    adminFolderOptions,
    adminFolders,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    importUploadForm,
    selectedAdminDocumentDetail: documentSelection.selectedAdminDocumentDetail,
    selectedDocumentId,
    selectedFolderId,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
  });
  const knowledgePermissionState = useKnowledgePermissions({
    activeDepartments: runtimeOptions.activeDepartments,
    adminDepartments: runtimeOptions.adminDepartments,
    adminKnowledgeBases,
    canImportDocuments: runtimeOptions.canImportDocuments,
    canIndexDocuments: runtimeOptions.canIndexDocuments,
    canManageFolders: runtimeOptions.canManageFolders,
    canManageKnowledgeBases: runtimeOptions.canManageKnowledgeBases,
    canManagePermissions: runtimeOptions.canManagePermissions,
    currentUser: runtimeOptions.currentUser,
    documentPermissionForm,
    folderCreateForm,
    folderDangerForm,
    formatDepartmentById,
    folderEditForm,
    importAdminBusy,
    importUploadForm,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBaseIndexForm,
    knowledgeBasePermissionForm,
    selectedAdminDocument: knowledgeDerivedState.selectedAdminDocument,
    selectedFolder: knowledgeDerivedState.selectedFolder,
    selectedImportFiles,
    selectedImportKnowledgeBase: knowledgeDerivedState.selectedImportKnowledgeBase,
    selectedKnowledgeBase: knowledgeDerivedState.selectedKnowledgeBase,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
  });
  const documentIndexState = useKnowledgeDocumentIndexState({
    canIndexDocuments: runtimeOptions.canIndexDocuments,
    documentIndexForm,
    importAdminBusy,
    selectedAdminDocument: knowledgeDerivedState.selectedAdminDocument,
    selectedBatchRebuildDocumentIds: documentSelection.selectedBatchRebuildDocumentIds,
    selectedCleanupPendingDeleteIndexVersionIds:
      documentSelection.selectedCleanupPendingDeleteIndexVersionIds,
  });
  const failedIndexJobState = useKnowledgeFailedIndexJobs({
    canIndexDocuments: runtimeOptions.canIndexDocuments,
    failedIndexJobs,
    importAdminBusy,
    indexRetryForm,
    selectedFailedIndexJobIds,
  });

  return {
    documentIndexState,
    documentSelection,
    failedIndexJobState,
    formatDepartmentById,
    knowledgeDerivedState,
    knowledgePermissionState,
  };
}
