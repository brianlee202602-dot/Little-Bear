import type { AdminKnowledgeBaseListResponse } from "@/api/knowledgeBases";
import type { PaginationState } from "@/utils/pagination";

type ValueRef<T> = {
  value: T;
};

export interface UseKnowledgeBaseAdminRefreshDependencies {
  adminDepartmentOptions: ValueRef<unknown[]>;
  adminDocuments: ValueRef<unknown[]>;
  adminFolderOptions: ValueRef<unknown[]>;
  adminFolders: ValueRef<unknown[]>;
  adminImportJobs: ValueRef<unknown[]>;
  adminKnowledgeBaseOptions: ValueRef<unknown[]>;
  adminKnowledgeBases: ValueRef<Array<{ id: string }>>;
  canLoadImportAdmin: ValueRef<boolean>;
  canManageDocuments: ValueRef<boolean>;
  canManageFolders: ValueRef<boolean>;
  canManageKnowledgeBases: ValueRef<boolean>;
  canReadDepartments: ValueRef<boolean>;
  canReadImportJobs: ValueRef<boolean>;
  clearPaginationState: (state: PaginationState) => void;
  clearSelectedDocumentDetails: () => void;
  clearSelectedDocumentMetadata: () => void;
  documentPagination: PaginationState;
  ensureAccessToken: () => Promise<string | null>;
  ensureImportKnowledgeBaseSelection: () => void;
  failedIndexJobPagination: PaginationState;
  failedIndexJobs: ValueRef<unknown[]>;
  folderPagination: PaginationState;
  importAdminBusy: {
    loading: boolean;
  };
  importAdminFeedback: ValueRef<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  knowledgeBasePagination: PaginationState;
  knowledgeBaseSearchForm: {
    keyword: string;
    status: string;
  };
  listAdminKnowledgeBases: (
    accessToken: string,
    filters: { keyword?: string; page?: number; page_size?: number; status?: string },
  ) => Promise<AdminKnowledgeBaseListResponse>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  refreshDepartmentOptions: (existingAccessToken?: string) => Promise<void>;
  refreshFailedIndexJobs: (existingAccessToken?: string) => Promise<boolean>;
  refreshImportJobList: (accessToken: string, fallbackKbId?: string) => Promise<void>;
  refreshKnowledgeBaseOptions: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseDetail: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseDocuments: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseFolders: (existingAccessToken?: string) => Promise<void>;
  selectedDocumentId: ValueRef<string>;
  selectedFailedIndexJobIds: ValueRef<string[]>;
  selectedFolderId: ValueRef<string>;
  selectedKnowledgeBaseDetail: ValueRef<unknown | null>;
  selectedKnowledgeBaseId: ValueRef<string>;
  syncPaginationState: (
    state: PaginationState,
    pagination: { page: number; page_size: number; total: number },
  ) => void;
}

export function useKnowledgeBaseAdminRefresh(
  options: UseKnowledgeBaseAdminRefreshDependencies,
) {
  const {
    adminDepartmentOptions,
    adminDocuments,
    adminFolderOptions,
    adminFolders,
    adminImportJobs,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    canLoadImportAdmin,
    canManageDocuments,
    canManageFolders,
    canManageKnowledgeBases,
    canReadDepartments,
    canReadImportJobs,
    clearPaginationState,
    clearSelectedDocumentDetails,
    clearSelectedDocumentMetadata,
    documentPagination,
    ensureAccessToken,
    ensureImportKnowledgeBaseSelection,
    failedIndexJobPagination,
    failedIndexJobs,
    folderPagination,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    knowledgeBasePagination,
    knowledgeBaseSearchForm,
    listAdminKnowledgeBases,
    normalizeErrorMessage,
    refreshDepartmentOptions,
    refreshFailedIndexJobs,
    refreshImportJobList,
    refreshKnowledgeBaseOptions,
    refreshSelectedKnowledgeBaseDetail,
    refreshSelectedKnowledgeBaseDocuments,
    refreshSelectedKnowledgeBaseFolders,
    selectedDocumentId,
    selectedFailedIndexJobIds,
    selectedFolderId,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
    syncPaginationState,
  } = options;

  async function refreshKnowledgeBaseAdminState(): Promise<void> {
    if (!canLoadImportAdmin.value) {
      adminKnowledgeBases.value = [];
      adminKnowledgeBaseOptions.value = [];
      selectedKnowledgeBaseDetail.value = null;
      clearPaginationState(knowledgeBasePagination);
      adminFolders.value = [];
      adminFolderOptions.value = [];
      clearPaginationState(folderPagination);
      adminDocuments.value = [];
      clearPaginationState(documentPagination);
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
      adminImportJobs.value = [];
      clearPaginationState(importJobPagination);
      failedIndexJobs.value = [];
      selectedFailedIndexJobIds.value = [];
      clearPaginationState(failedIndexJobPagination);
      selectedKnowledgeBaseId.value = "";
      selectedFolderId.value = "";
      selectedDocumentId.value = "";
      importAdminFeedback.value = {
        tone: "error",
        message: "当前账号缺少知识库、文件夹、文档、权限或导入任务读取权限。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.loading = true;
    let failedIndexJobsLoaded = true;
    try {
      if (canReadDepartments.value) {
        await refreshDepartmentOptions(accessToken);
      } else {
        adminDepartmentOptions.value = [];
      }
      if (canManageKnowledgeBases.value) {
        await refreshKnowledgeBaseOptions(accessToken);
        const previousSelectedKnowledgeBaseId = selectedKnowledgeBaseId.value;
        const knowledgeBasesResponse = await listAdminKnowledgeBases(accessToken, {
          keyword: knowledgeBaseSearchForm.keyword.trim() || undefined,
          status: knowledgeBaseSearchForm.status || undefined,
          page: knowledgeBasePagination.page,
          page_size: knowledgeBasePagination.pageSize,
        });
        adminKnowledgeBases.value = knowledgeBasesResponse.data;
        syncPaginationState(knowledgeBasePagination, knowledgeBasesResponse.pagination);
        if (
          !selectedKnowledgeBaseId.value ||
          !adminKnowledgeBases.value.some(
            (knowledgeBase: { id: string }) => knowledgeBase.id === selectedKnowledgeBaseId.value,
          )
        ) {
          selectedKnowledgeBaseId.value = adminKnowledgeBases.value[0]?.id ?? "";
          selectedKnowledgeBaseDetail.value = null;
        }
        if (selectedKnowledgeBaseId.value !== previousSelectedKnowledgeBaseId) {
          selectedFolderId.value = "";
          selectedDocumentId.value = "";
          clearPaginationState(folderPagination);
          clearPaginationState(documentPagination);
          clearSelectedDocumentDetails();
          clearSelectedDocumentMetadata();
        }
        ensureImportKnowledgeBaseSelection();
        if (selectedKnowledgeBaseId.value) {
          await refreshSelectedKnowledgeBaseDetail(accessToken);
        } else {
          selectedKnowledgeBaseDetail.value = null;
        }
        if (canManageFolders.value) {
          await refreshSelectedKnowledgeBaseFolders(accessToken);
        } else {
          adminFolders.value = [];
          adminFolderOptions.value = [];
          clearPaginationState(folderPagination);
          selectedFolderId.value = "";
        }
        if (canManageDocuments.value) {
          await refreshSelectedKnowledgeBaseDocuments(accessToken);
        } else {
          adminDocuments.value = [];
          clearPaginationState(documentPagination);
          selectedDocumentId.value = "";
          clearSelectedDocumentDetails();
          clearSelectedDocumentMetadata();
        }
      } else {
        clearPaginationState(knowledgeBasePagination);
        adminKnowledgeBaseOptions.value = [];
        selectedKnowledgeBaseDetail.value = null;
        adminFolders.value = [];
        adminFolderOptions.value = [];
        clearPaginationState(folderPagination);
        adminDocuments.value = [];
        clearPaginationState(documentPagination);
        selectedFolderId.value = "";
        selectedDocumentId.value = "";
        clearSelectedDocumentDetails();
        clearSelectedDocumentMetadata();
      }
      if (canReadImportJobs.value) {
        await refreshImportJobList(accessToken);
        failedIndexJobsLoaded = await refreshFailedIndexJobs(accessToken);
      } else {
        adminImportJobs.value = [];
        clearPaginationState(importJobPagination);
        failedIndexJobs.value = [];
        selectedFailedIndexJobIds.value = [];
        clearPaginationState(failedIndexJobPagination);
      }
      if (failedIndexJobsLoaded) {
        importAdminFeedback.value = {
          tone: "success",
          message: "知识库管理数据已刷新。",
        };
      }
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取知识库管理数据失败"),
      };
    } finally {
      importAdminBusy.loading = false;
    }
  }

  return { refreshKnowledgeBaseAdminState };
}
