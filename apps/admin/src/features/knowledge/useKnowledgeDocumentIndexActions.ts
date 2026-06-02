import type { ComputedRef, Ref } from "vue";

import type { AcceptedResponse } from "@/api/commonTypes";
import type { PaginationState } from "@/utils/pagination";

interface UseKnowledgeDocumentIndexActionsDependencies {
  canCleanupSelectedIndexVersions: ComputedRef<boolean>;
  canLoadIndexOps: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canRebuildSelectedDocumentIndex: ComputedRef<boolean>;
  canRebuildSelectedDocumentsIndex: ComputedRef<boolean>;
  clearBatchDocumentSelection: () => void;
  clearIndexVersionCleanupSelection: () => void;
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
  documentIndexForm: {
    confirmedRebuild: boolean;
  };
  ensureAccessToken: () => Promise<string | null>;
  importAdminBusy: {
    cleaningIndexVersions: boolean;
    rebuildingBatchIndex: boolean;
    rebuildingIndex: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  refreshImportJobList: (accessToken: string, fallbackKbId?: string) => Promise<void>;
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedDocumentIndexVersions: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseDocuments: (existingAccessToken?: string) => Promise<void>;
  selectedAdminDocument: ComputedRef<{ id: string } | null>;
  selectedBatchRebuildDocumentIds: ComputedRef<string[]>;
  selectedCleanupPendingDeleteIndexVersionIds: ComputedRef<string[]>;
  selectedKnowledgeBase: ComputedRef<{ id: string } | null>;
}

export function useKnowledgeDocumentIndexActions(
  options: UseKnowledgeDocumentIndexActionsDependencies,
) {
  const {
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
  } = options;

  async function rebuildSelectedDocumentIndex(): Promise<void> {
    const document = selectedAdminDocument.value;
    if (!document || !canRebuildSelectedDocumentIndex.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "重建索引前必须选择 active 文档、确认当前版本存在，并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.rebuildingIndex = true;
    try {
      const response = await createAdminDocumentIndexJob(document.id, accessToken, true);
      documentIndexForm.confirmedRebuild = false;
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
      if (canReadImportJobs.value) {
        importJobPagination.page = 1;
        await refreshImportJobList(accessToken);
      }
      importAdminFeedback.value = {
        tone: "success",
        message: `索引重建任务已创建：${response.data.job_id ?? "-"}`,
      };
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "创建索引重建任务失败"),
      };
    } finally {
      importAdminBusy.rebuildingIndex = false;
    }
  }

  async function rebuildSelectedDocumentsIndex(): Promise<void> {
    const documentIds = selectedBatchRebuildDocumentIds.value;
    if (!canRebuildSelectedDocumentsIndex.value || documentIds.length === 0) {
      importAdminFeedback.value = {
        tone: "error",
        message: "批量重建索引前必须选择可重建文档，并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.rebuildingBatchIndex = true;
    try {
      const response = await createAdminIndexJob({ document_ids: documentIds }, accessToken, true);
      clearBatchDocumentSelection();
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
      if (canReadImportJobs.value) {
        importJobPagination.page = 1;
        await refreshImportJobList(accessToken, selectedKnowledgeBase.value?.id);
      }
      if (canLoadIndexOps.value) {
        await refreshIndexHealth(accessToken);
      }
      importAdminFeedback.value = {
        tone: "success",
        message: `已为 ${documentIds.length} 个文档创建批量索引重建任务：${response.data.job_id ?? "-"}`,
      };
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "创建批量索引重建任务失败"),
      };
    } finally {
      importAdminBusy.rebuildingBatchIndex = false;
    }
  }

  async function cleanupSelectedIndexVersions(): Promise<void> {
    const indexVersionIds = selectedCleanupPendingDeleteIndexVersionIds.value;
    if (!canCleanupSelectedIndexVersions.value || indexVersionIds.length === 0) {
      importAdminFeedback.value = {
        tone: "error",
        message: "清理索引前必须选择 pending_delete 索引版本，并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.cleaningIndexVersions = true;
    try {
      const response = await createAdminIndexVersionCleanupJob(
        { index_version_ids: indexVersionIds },
        accessToken,
        true,
      );
      clearIndexVersionCleanupSelection();
      await refreshSelectedDocumentIndexVersions(accessToken);
      if (canReadImportJobs.value) {
        importJobPagination.page = 1;
        await refreshImportJobList(accessToken, selectedKnowledgeBase.value?.id);
      }
      if (canLoadIndexOps.value) {
        await refreshIndexHealth(accessToken);
      }
      importAdminFeedback.value = {
        tone: "success",
        message: `已创建 ${indexVersionIds.length} 个索引版本的清理任务：${response.data.job_id ?? "-"}`,
      };
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "创建索引清理任务失败"),
      };
    } finally {
      importAdminBusy.cleaningIndexVersions = false;
    }
  }

  return {
    cleanupSelectedIndexVersions,
    rebuildSelectedDocumentIndex,
    rebuildSelectedDocumentsIndex,
  };
}
