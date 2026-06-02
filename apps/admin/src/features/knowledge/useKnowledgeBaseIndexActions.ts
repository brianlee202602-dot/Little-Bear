import type { ComputedRef, Ref } from "vue";

import type { AcceptedResponse } from "@/api/indexOps";
import type { PaginationState } from "@/utils/pagination";

type UseKnowledgeBaseIndexActionsOptions = {
  canLoadIndexOps: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canRebuildSelectedKnowledgeBaseIndex: ComputedRef<boolean>;
  closeKnowledgeBaseModal: () => void;
  createAdminIndexJob: (
    payload: { kb_id: string },
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  ensureAccessToken: () => Promise<string | null>;
  importAdminBusy: {
    rebuildingIndex: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importJobPagination: PaginationState;
  knowledgeBaseIndexForm: {
    confirmedRebuild: boolean;
  };
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  refreshImportJobList: (accessToken: string, fallbackKbId?: string) => Promise<void>;
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseDocuments: (existingAccessToken?: string) => Promise<void>;
  selectedKnowledgeBase: ComputedRef<{ id: string } | null>;
};

export function useKnowledgeBaseIndexActions(options: UseKnowledgeBaseIndexActionsOptions) {
  async function rebuildSelectedKnowledgeBaseIndex(): Promise<void> {
    const knowledgeBase = options.selectedKnowledgeBase.value;
    if (!knowledgeBase || !options.canRebuildSelectedKnowledgeBaseIndex.value) {
      options.importAdminFeedback.value = {
        tone: "error",
        message: "重建知识库索引前必须选择 active 知识库，并勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.importAdminBusy.rebuildingIndex = true;
    try {
      const response = await options.createAdminIndexJob(
        { kb_id: knowledgeBase.id },
        accessToken,
        true,
      );
      options.knowledgeBaseIndexForm.confirmedRebuild = false;
      await options.refreshSelectedKnowledgeBaseDocuments(accessToken);
      if (options.canReadImportJobs.value) {
        options.importJobPagination.page = 1;
        await options.refreshImportJobList(accessToken, knowledgeBase.id);
      }
      if (options.canLoadIndexOps.value) {
        await options.refreshIndexHealth(accessToken);
      }
      options.importAdminFeedback.value = {
        tone: "success",
        message: `知识库索引重建任务已创建：${response.data.job_id ?? "-"}`,
      };
      options.closeKnowledgeBaseModal();
    } catch (error) {
      options.importAdminFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "创建知识库索引重建任务失败"),
      };
    } finally {
      options.importAdminBusy.rebuildingIndex = false;
    }
  }

  return {
    rebuildSelectedKnowledgeBaseIndex,
  };
}
