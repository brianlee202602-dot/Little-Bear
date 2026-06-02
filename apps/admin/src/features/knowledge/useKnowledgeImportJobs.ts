import type { ComputedRef, Ref } from "vue";

import type { ImportJobListResponse, ImportJobListItemData } from "@/api/imports";
import type { PaginationState } from "@/utils/pagination";

export interface UseKnowledgeImportJobsDependencies {
  adminImportJobs: Ref<ImportJobListItemData[]>;
  canReadImportJobs: ComputedRef<boolean>;
  canRetrySelectedFailedIndexJobs: ComputedRef<boolean>;
  clearPaginationState: (state: PaginationState) => void;
  ensureAccessToken: () => Promise<string | null>;
  failedIndexJobPagination: PaginationState;
  failedIndexJobs: Ref<ImportJobListItemData[]>;
  importAdminBusy: {
    loadingFailedIndexJobs: boolean;
    retryingIndexJobs: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  importSearchForm: {
    jobType: string;
    kbId: string;
    stage: string;
    status: string;
  };
  indexRetryForm: {
    confirmedRetry: boolean;
  };
  listAdminImportJobs: (
    accessToken: string,
    filters: {
      job_type?: string;
      kb_id?: string;
      page?: number;
      page_size?: number;
      stage?: string;
      status?: string;
    },
  ) => Promise<ImportJobListResponse>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  paginationTotalPages: (state: PaginationState) => number;
  refreshKnowledgeBaseAdminState: () => Promise<void>;
  retryAdminIndexJobs: (
    payload: { job_ids: string[] },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<ImportJobListResponse>;
  selectedFailedIndexJobIds: Ref<string[]>;
  syncPaginationState: (
    state: PaginationState,
    pagination: { page: number; page_size: number; total: number },
  ) => void;
}

export function useKnowledgeImportJobs(options: UseKnowledgeImportJobsDependencies) {
  const {
    adminImportJobs,
    canReadImportJobs,
    canRetrySelectedFailedIndexJobs,
    clearPaginationState,
    ensureAccessToken,
    failedIndexJobPagination,
    failedIndexJobs,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    importSearchForm,
    indexRetryForm,
    listAdminImportJobs,
    normalizeErrorMessage,
    paginationTotalPages,
    refreshKnowledgeBaseAdminState,
    retryAdminIndexJobs,
    selectedFailedIndexJobIds,
    syncPaginationState,
  } = options;

  async function refreshImportJobList(
    accessToken: string,
    fallbackKbId?: string,
  ): Promise<void> {
    if (!canReadImportJobs.value) {
      adminImportJobs.value = [];
      clearPaginationState(importJobPagination);
      return;
    }
    const jobsResponse = await listAdminImportJobs(accessToken, {
      page: importJobPagination.page,
      page_size: importJobPagination.pageSize,
      kb_id: importSearchForm.kbId || fallbackKbId || undefined,
      job_type: importSearchForm.jobType || undefined,
      status: importSearchForm.status || undefined,
      stage: importSearchForm.stage || undefined,
    });
    adminImportJobs.value = jobsResponse.data;
    syncPaginationState(importJobPagination, jobsResponse.pagination);
  }

  function refreshImportTaskFilters(): void {
    importJobPagination.page = 1;
    failedIndexJobPagination.page = 1;
    void refreshKnowledgeBaseAdminState();
  }

  async function refreshFailedIndexJobs(existingAccessToken?: string): Promise<boolean> {
    if (!canReadImportJobs.value) {
      failedIndexJobs.value = [];
      selectedFailedIndexJobIds.value = [];
      clearPaginationState(failedIndexJobPagination);
      return true;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return false;
    }

    importAdminBusy.loadingFailedIndexJobs = true;
    try {
      const response = await listAdminImportJobs(accessToken, {
        kb_id: importSearchForm.kbId || undefined,
        status: "failed",
        job_type: "index_rebuild",
        page: failedIndexJobPagination.page,
        page_size: failedIndexJobPagination.pageSize,
      });
      failedIndexJobs.value = response.data;
      syncPaginationState(failedIndexJobPagination, response.pagination);
      if (
        failedIndexJobs.value.length === 0 &&
        failedIndexJobPagination.total > 0 &&
        failedIndexJobPagination.page > 1
      ) {
        failedIndexJobPagination.page = paginationTotalPages(failedIndexJobPagination);
        return refreshFailedIndexJobs(accessToken);
      }
      const availableIds = new Set(response.data.map((job) => job.id));
      selectedFailedIndexJobIds.value = selectedFailedIndexJobIds.value.filter((id) =>
        availableIds.has(id),
      );
      if (selectedFailedIndexJobIds.value.length === 0) {
        indexRetryForm.confirmedRetry = false;
      }
      return true;
    } catch (error) {
      failedIndexJobs.value = [];
      selectedFailedIndexJobIds.value = [];
      clearPaginationState(failedIndexJobPagination);
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取失败索引任务失败"),
      };
      return false;
    } finally {
      importAdminBusy.loadingFailedIndexJobs = false;
    }
  }

  async function refreshFailedIndexJobsPage(): Promise<void> {
    await refreshFailedIndexJobs();
  }

  function toggleFailedIndexJob(jobId: string, checked: boolean): void {
    const next = new Set(selectedFailedIndexJobIds.value);
    if (checked) {
      next.add(jobId);
    } else {
      next.delete(jobId);
    }
    selectedFailedIndexJobIds.value = Array.from(next);
    if (selectedFailedIndexJobIds.value.length === 0) {
      indexRetryForm.confirmedRetry = false;
    }
  }

  function onFailedIndexJobToggle(jobId: string, event: Event): void {
    toggleFailedIndexJob(jobId, (event.target as HTMLInputElement).checked);
  }

  function toggleAllFailedIndexJobs(checked: boolean): void {
    selectedFailedIndexJobIds.value = checked ? failedIndexJobs.value.map((job) => job.id) : [];
    if (!checked) {
      indexRetryForm.confirmedRetry = false;
    }
  }

  function onAllFailedIndexJobsToggle(event: Event): void {
    toggleAllFailedIndexJobs((event.target as HTMLInputElement).checked);
  }

  async function retrySelectedFailedIndexJobs(): Promise<void> {
    if (!canRetrySelectedFailedIndexJobs.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "批量重试前必须选择失败索引任务，并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.retryingIndexJobs = true;
    try {
      const response = await retryAdminIndexJobs(
        { job_ids: selectedFailedIndexJobIds.value },
        accessToken,
        true,
      );
      indexRetryForm.confirmedRetry = false;
      selectedFailedIndexJobIds.value = [];
      await refreshKnowledgeBaseAdminState();
      importAdminFeedback.value = {
        tone: "success",
        message: `已创建 ${response.data.length} 个索引重试任务。`,
      };
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "批量重试索引任务失败"),
      };
    } finally {
      importAdminBusy.retryingIndexJobs = false;
    }
  }

  return {
    onAllFailedIndexJobsToggle,
    onFailedIndexJobToggle,
    refreshFailedIndexJobs,
    refreshFailedIndexJobsPage,
    refreshImportJobList,
    refreshImportTaskFilters,
    retrySelectedFailedIndexJobs,
  };
}
