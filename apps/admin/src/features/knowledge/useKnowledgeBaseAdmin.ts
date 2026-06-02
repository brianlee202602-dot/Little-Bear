import {
  useKnowledgeDocuments,
  type UseKnowledgeDocumentsDependencies,
} from "@/features/knowledge/useKnowledgeDocuments";
import {
  useKnowledgeBaseAccessSelection,
  type UseKnowledgeBaseAccessSelectionDependencies,
} from "@/features/knowledge/useKnowledgeBaseAccessSelection";
import {
  useKnowledgeBaseAdminRefresh,
  type UseKnowledgeBaseAdminRefreshDependencies,
} from "@/features/knowledge/useKnowledgeBaseAdminRefresh";
import {
  useKnowledgeBaseRecords,
  type UseKnowledgeBaseRecordsDependencies,
} from "@/features/knowledge/useKnowledgeBaseRecords";
import {
  useKnowledgeFolders,
  type UseKnowledgeFoldersDependencies,
} from "@/features/knowledge/useKnowledgeFolders";
import {
  useKnowledgeImportJobs,
  type UseKnowledgeImportJobsDependencies,
} from "@/features/knowledge/useKnowledgeImportJobs";
import {
  useKnowledgeOptions,
  type UseKnowledgeOptionsDependencies,
} from "@/features/knowledge/useKnowledgeOptions";
import {
  useKnowledgeBaseUpload,
  type UseKnowledgeBaseUploadDependencies,
} from "@/features/knowledge/useKnowledgeBaseUpload";

type UseKnowledgeBaseAdminOptions =
  UseKnowledgeOptionsDependencies &
  Omit<UseKnowledgeImportJobsDependencies, "refreshKnowledgeBaseAdminState"> &
  Omit<UseKnowledgeDocumentsDependencies, "refreshImportJobList"> &
  Omit<
    UseKnowledgeFoldersDependencies,
    "refreshFolderOptions" | "refreshSelectedKnowledgeBaseDocuments"
  > &
  Omit<
    UseKnowledgeBaseRecordsDependencies,
    | "refreshImportJobList"
    | "refreshKnowledgeBaseAdminState"
    | "refreshSelectedKnowledgeBaseDocuments"
    | "refreshSelectedKnowledgeBaseFolders"
    | "clearSelectedDocumentMetadata"
  > &
  UseKnowledgeBaseAccessSelectionDependencies &
  Omit<
    UseKnowledgeBaseUploadDependencies,
    "closeKnowledgeBaseModal" | "refreshKnowledgeBaseAdminState" | "selectKnowledgeBase"
  > &
  Omit<
    UseKnowledgeBaseAdminRefreshDependencies,
    | "ensureImportKnowledgeBaseSelection"
    | "refreshFailedIndexJobs"
    | "refreshImportJobList"
    | "refreshKnowledgeBaseOptions"
    | "refreshSelectedKnowledgeBaseDetail"
    | "refreshSelectedKnowledgeBaseDocuments"
    | "refreshSelectedKnowledgeBaseFolders"
    | "clearSelectedDocumentMetadata"
  > & {
    onAllBatchDocumentsToggle: (event: Event) => void;
    onAllIndexVersionsForCleanupToggle: (event: Event) => void;
    onBatchDocumentSelectionToggle: (documentId: string, event: Event) => void;
    onIndexVersionCleanupSelectionToggle: (indexVersionId: string, event: Event) => void;
  };

export function useKnowledgeBaseAdmin(options: UseKnowledgeBaseAdminOptions) {
const {
  refreshFolderOptions,
  refreshFolderOptionsFromSearch,
  refreshKnowledgeBaseOptions,
  refreshKnowledgeBaseOptionsFromSearch,
} = useKnowledgeOptions({
  ...options,
});

const {
  onAllFailedIndexJobsToggle,
  onFailedIndexJobToggle,
  refreshFailedIndexJobs,
  refreshFailedIndexJobsPage,
  refreshImportJobList,
  refreshImportTaskFilters,
  retrySelectedFailedIndexJobs,
} = useKnowledgeImportJobs({
  ...options,
  refreshKnowledgeBaseAdminState,
});

const {
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
} = useKnowledgeDocuments({
  ...options,
  refreshImportJobList,
});

const {
  closeFolderModal,
  deleteSelectedFolder,
  openCreateFolderModal,
  openDeleteFolderModal,
  openEditFolderModal,
  refreshSelectedKnowledgeBaseFolders,
  submitCreateFolder,
  submitPatchFolder,
} = useKnowledgeFolders({
  ...options,
  refreshFolderOptions,
  refreshSelectedKnowledgeBaseDocuments,
});

const {
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
} = useKnowledgeBaseRecords({
  ...options,
  clearSelectedDocumentMetadata,
  refreshImportJobList,
  refreshKnowledgeBaseAdminState,
  refreshSelectedKnowledgeBaseDocuments,
  refreshSelectedKnowledgeBaseFolders,
});

const {
  onKnowledgeBaseCreateAccessDepartmentChange,
  onKnowledgeBasePermissionAccessDepartmentChange,
} = useKnowledgeBaseAccessSelection({
  ...options,
});

const {
  clearImportFiles,
  ensureImportKnowledgeBaseSelection,
  onImportFilesChange,
  openUploadKnowledgeBaseModal,
  submitDocumentUpload,
} = useKnowledgeBaseUpload({
  ...options,
  closeKnowledgeBaseModal,
  refreshKnowledgeBaseAdminState,
  selectKnowledgeBase,
});

const knowledgeBaseAdminRefresh = useKnowledgeBaseAdminRefresh({
  ...options,
  clearSelectedDocumentMetadata,
  ensureImportKnowledgeBaseSelection,
  refreshFailedIndexJobs,
  refreshImportJobList,
  refreshKnowledgeBaseOptions,
  refreshSelectedKnowledgeBaseDetail,
  refreshSelectedKnowledgeBaseDocuments,
  refreshSelectedKnowledgeBaseFolders,
});

async function refreshKnowledgeBaseAdminState(): Promise<void> {
  return knowledgeBaseAdminRefresh.refreshKnowledgeBaseAdminState();
}

  return {
    refreshKnowledgeBaseOptions,
    refreshFolderOptions,
    refreshKnowledgeBaseOptionsFromSearch,
    refreshFolderOptionsFromSearch,
    refreshImportJobList,
    refreshImportTaskFilters,
    refreshKnowledgeBaseAdminState,
    refreshFailedIndexJobs,
    refreshFailedIndexJobsPage,
    onFailedIndexJobToggle,
    onAllFailedIndexJobsToggle,
    retrySelectedFailedIndexJobs,
    refreshSelectedKnowledgeBaseDetail,
    refreshSelectedKnowledgeBaseFolders,
    clearSelectedDocumentDetails: options.clearSelectedDocumentDetails,
    clearSelectedDocumentMetadata,
    clearBatchDocumentSelection: options.clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection: options.clearIndexVersionCleanupSelection,
    refreshSelectedKnowledgeBaseDocuments,
    refreshSelectedDocumentDetails,
    refreshSelectedDocumentMetadata,
    refreshSelectedDocumentVersions,
    refreshSelectedDocumentIndexVersions,
    onBatchDocumentSelectionToggle: options.onBatchDocumentSelectionToggle,
    onAllBatchDocumentsToggle: options.onAllBatchDocumentsToggle,
    onIndexVersionCleanupSelectionToggle: options.onIndexVersionCleanupSelectionToggle,
    onAllIndexVersionsForCleanupToggle: options.onAllIndexVersionsForCleanupToggle,
    openCreateKnowledgeBaseModal,
    openEditKnowledgeBaseModal,
    openDeleteKnowledgeBaseModal,
    openKnowledgeBasePermissionsModal,
    openRebuildKnowledgeBaseIndexModal,
    openKnowledgeBaseDocumentManagerModal,
    closeKnowledgeBaseDocumentManagerModal,
    openUploadKnowledgeBaseModal,
    closeKnowledgeBaseModal,
    openCreateFolderModal,
    openEditFolderModal,
    openDeleteFolderModal,
    closeFolderModal,
    onImportFilesChange,
    clearImportFiles,
    submitDocumentUpload,
    submitCreateKnowledgeBase,
    submitCreateFolder,
    submitPatchFolder,
    deleteSelectedFolder,
    selectKnowledgeBase,
    submitPatchKnowledgeBase,
    submitKnowledgeBasePermissions,
    deleteSelectedKnowledgeBase,
    rebuildSelectedKnowledgeBaseIndex,
    upsertKnowledgeBase,
    openDocumentDetailsModal,
    openDocumentPermissionsModal,
    closeDocumentModal,
    submitDocumentPermissions,
    rebuildSelectedDocumentIndex,
    rebuildSelectedDocumentsIndex,
    cleanupSelectedIndexVersions,
    onKnowledgeBaseCreateAccessDepartmentChange,
    onKnowledgeBasePermissionAccessDepartmentChange,
  };
}
