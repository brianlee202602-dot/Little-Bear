import type { Ref } from "vue";

import type { PaginationState } from "@/utils/pagination";

type NullableMode = string | null;

type ResetOptions = {
  adminDocuments: Ref<unknown[]>;
  adminFolderOptions: Ref<unknown[]>;
  adminFolders: Ref<unknown[]>;
  adminImportJobs: Ref<unknown[]>;
  adminKnowledgeBaseOptions: Ref<unknown[]>;
  adminKnowledgeBases: Ref<unknown[]>;
  clearPaginationState: (state: PaginationState) => void;
  clearSelectedDocumentDetails: () => void;
  clearSelectedDocumentMetadata: () => void;
  documentIndexForm: {
    confirmedRebuild: boolean;
    confirmedBatchRebuild: boolean;
    confirmedCleanup: boolean;
  };
  documentManagerModalOpen: Ref<boolean>;
  documentModalMode: Ref<NullableMode>;
  documentPagination: PaginationState;
  documentPermissionForm: { confirmedReplace: boolean };
  documentSearchForm: { status: string };
  failedIndexJobPagination: PaginationState;
  failedIndexJobs: Ref<unknown[]>;
  folderDangerForm: { confirmedDelete: boolean };
  folderModalMode: Ref<NullableMode>;
  folderPagination: PaginationState;
  importAdminFeedback: Ref<unknown | null>;
  importJobPagination: PaginationState;
  importSearchForm: {
    kbId: string;
    jobType: string;
    status: string;
    stage: string;
  };
  importUploadForm: {
    kbId: string;
    folderId: string;
    idempotencyKey: string;
  };
  indexRetryForm: { confirmedRetry: boolean };
  knowledgeBaseDangerForm: { confirmedDelete: boolean };
  knowledgeBaseIndexForm: { confirmedRebuild: boolean };
  knowledgeBaseModalMode: Ref<NullableMode>;
  knowledgeBasePagination: PaginationState;
  knowledgeBasePermissionForm: { confirmedReplace: boolean };
  knowledgeBaseSearchForm: { keyword: string; status: string };
  selectedBatchDocumentIds: Ref<string[]>;
  selectedDocumentId: Ref<string>;
  selectedFailedIndexJobIds: Ref<string[]>;
  selectedFolderId: Ref<string>;
  selectedImportFiles: Ref<File[]>;
  selectedKnowledgeBaseDetail: Ref<unknown | null>;
  selectedKnowledgeBaseId: Ref<string>;
};

export function useKnowledgeAdminReset(options: ResetOptions) {
  function clearKnowledgeAdminState(): void {
    options.documentManagerModalOpen.value = false;
    options.adminKnowledgeBases.value = [];
    options.adminKnowledgeBaseOptions.value = [];
    options.selectedKnowledgeBaseDetail.value = null;
    options.adminFolders.value = [];
    options.adminFolderOptions.value = [];
    options.clearPaginationState(options.folderPagination);
    options.adminDocuments.value = [];
    options.clearPaginationState(options.documentPagination);
    options.clearSelectedDocumentDetails();
    options.clearSelectedDocumentMetadata();
    options.adminImportJobs.value = [];
    options.failedIndexJobs.value = [];
    options.selectedFailedIndexJobIds.value = [];
    options.clearPaginationState(options.failedIndexJobPagination);
    options.selectedBatchDocumentIds.value = [];
    options.selectedKnowledgeBaseId.value = "";
    options.selectedFolderId.value = "";
    options.selectedDocumentId.value = "";
    options.selectedImportFiles.value = [];
    options.clearPaginationState(options.knowledgeBasePagination);
    options.clearPaginationState(options.importJobPagination);
    options.knowledgeBaseSearchForm.keyword = "";
    options.knowledgeBaseSearchForm.status = "";
    options.knowledgeBaseModalMode.value = null;
    options.folderModalMode.value = null;
    options.documentModalMode.value = null;
    options.knowledgeBaseDangerForm.confirmedDelete = false;
    options.folderDangerForm.confirmedDelete = false;
    options.knowledgeBasePermissionForm.confirmedReplace = false;
    options.documentPermissionForm.confirmedReplace = false;
    options.knowledgeBaseIndexForm.confirmedRebuild = false;
    options.documentIndexForm.confirmedRebuild = false;
    options.documentIndexForm.confirmedBatchRebuild = false;
    options.documentIndexForm.confirmedCleanup = false;
    options.indexRetryForm.confirmedRetry = false;
    options.importUploadForm.kbId = "";
    options.importUploadForm.folderId = "";
    options.importUploadForm.idempotencyKey = "";
    options.importSearchForm.kbId = "";
    options.importSearchForm.jobType = "";
    options.importSearchForm.status = "";
    options.importSearchForm.stage = "";
    options.documentSearchForm.status = "";
    options.importAdminFeedback.value = null;
  }

  function clearKnowledgeBaseOptions(): void {
    options.adminKnowledgeBaseOptions.value = [];
  }

  return {
    clearKnowledgeAdminState,
    clearKnowledgeBaseOptions,
  };
}
