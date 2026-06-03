import type { Ref } from "vue";

import type { PaginationData } from "@/api/commonTypes";
import {
  getModelCallLog,
  getQueryLog,
  listModelCallLogs,
  listQueryLogs,
  type ModelCallLogData,
  type ModelCallLogListItemData,
  type QueryLogData,
  type QueryLogListItemData,
} from "@/api/diagnostics";
import type { DiagnosticsPaginationState } from "@/features/diagnostics/useDiagnostics";

type UseLogDiagnosticsOptions = {
  canLoadDiagnostics: { readonly value: boolean };
  clearPaginationState: (state: DiagnosticsPaginationState) => void;
  diagnosticsBusy: {
    loadingModelCallDetail: boolean;
    loadingModelCallLogs: boolean;
    loadingQueryDetail: boolean;
    loadingQueryLogs: boolean;
  };
  diagnosticsFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  ensureAccessToken: () => Promise<string | null>;
  modelCallLogDetailModalOpen: Ref<boolean>;
  modelCallLogPagination: DiagnosticsPaginationState;
  modelCallLogs: Ref<ModelCallLogListItemData[]>;
  modelCallSearchForm: {
    caller: string;
    degraded: string;
    errorCode: string;
    model: string;
    modelType: string;
    requestId: string;
    status: string;
    traceId: string;
  };
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  queryLogDetailModalOpen: Ref<boolean>;
  queryLogPagination: DiagnosticsPaginationState;
  queryLogs: Ref<QueryLogListItemData[]>;
  queryLogSearchForm: {
    degraded: string;
    degradeReason: string;
    errorCode: string;
    kbId: string;
    requestId: string;
    queryScopeMode: string;
    status: string;
    traceId: string;
    userId: string;
  };
  selectedModelCallLog: Ref<ModelCallLogData | null>;
  selectedQueryLog: Ref<QueryLogData | null>;
  syncPaginationState: (
    state: DiagnosticsPaginationState,
    pagination: PaginationData,
  ) => void;
};

function parseBooleanFilter(value: string): boolean | null {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return null;
}

export function useLogDiagnostics(options: UseLogDiagnosticsOptions) {
  async function refreshQueryLogs(existingAccessToken?: string): Promise<void> {
    if (!options.canLoadDiagnostics.value) {
      options.queryLogs.value = [];
      options.clearPaginationState(options.queryLogPagination);
      options.selectedQueryLog.value = null;
      options.queryLogDetailModalOpen.value = false;
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.loadingQueryLogs = true;
    try {
      const response = await listQueryLogs(accessToken, {
        page: options.queryLogPagination.page,
        page_size: options.queryLogPagination.pageSize,
        user_id: options.queryLogSearchForm.userId.trim() || undefined,
        kb_id: options.queryLogSearchForm.kbId.trim() || undefined,
        status: options.queryLogSearchForm.status || undefined,
        query_scope_mode: options.queryLogSearchForm.queryScopeMode || undefined,
        degraded: parseBooleanFilter(options.queryLogSearchForm.degraded),
        degrade_reason: options.queryLogSearchForm.degradeReason.trim() || undefined,
        request_id: options.queryLogSearchForm.requestId.trim() || undefined,
        trace_id: options.queryLogSearchForm.traceId.trim() || undefined,
        error_code: options.queryLogSearchForm.errorCode.trim() || undefined,
      });
      options.queryLogs.value = response.data;
      options.syncPaginationState(options.queryLogPagination, response.pagination);
      if (
        options.selectedQueryLog.value &&
        !options.queryLogs.value.some(
          (log) => log.id === options.selectedQueryLog.value?.id,
        )
      ) {
        options.selectedQueryLog.value = null;
        options.queryLogDetailModalOpen.value = false;
      }
      options.diagnosticsFeedback.value = null;
    } catch (error) {
      options.queryLogs.value = [];
      options.clearPaginationState(options.queryLogPagination);
      options.selectedQueryLog.value = null;
      options.queryLogDetailModalOpen.value = false;
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取查询日志失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingQueryLogs = false;
    }
  }

  async function refreshModelCallLogs(existingAccessToken?: string): Promise<void> {
    if (!options.canLoadDiagnostics.value) {
      options.modelCallLogs.value = [];
      options.clearPaginationState(options.modelCallLogPagination);
      options.selectedModelCallLog.value = null;
      options.modelCallLogDetailModalOpen.value = false;
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.loadingModelCallLogs = true;
    try {
      const response = await listModelCallLogs(accessToken, {
        page: options.modelCallLogPagination.page,
        page_size: options.modelCallLogPagination.pageSize,
        model: options.modelCallSearchForm.model.trim() || undefined,
        model_type: options.modelCallSearchForm.modelType.trim() || undefined,
        caller: options.modelCallSearchForm.caller.trim() || undefined,
        status: options.modelCallSearchForm.status || undefined,
        degraded: parseBooleanFilter(options.modelCallSearchForm.degraded),
        request_id: options.modelCallSearchForm.requestId.trim() || undefined,
        trace_id: options.modelCallSearchForm.traceId.trim() || undefined,
        error_code: options.modelCallSearchForm.errorCode.trim() || undefined,
      });
      options.modelCallLogs.value = response.data;
      options.syncPaginationState(options.modelCallLogPagination, response.pagination);
      if (
        options.selectedModelCallLog.value &&
        !options.modelCallLogs.value.some(
          (log) => log.id === options.selectedModelCallLog.value?.id,
        )
      ) {
        options.selectedModelCallLog.value = null;
        options.modelCallLogDetailModalOpen.value = false;
      }
      options.diagnosticsFeedback.value = null;
    } catch (error) {
      options.modelCallLogs.value = [];
      options.clearPaginationState(options.modelCallLogPagination);
      options.selectedModelCallLog.value = null;
      options.modelCallLogDetailModalOpen.value = false;
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取模型调用日志失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingModelCallLogs = false;
    }
  }

  async function selectQueryLog(queryLogId: string): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    options.diagnosticsBusy.loadingQueryDetail = true;
    try {
      const response = await getQueryLog(queryLogId, accessToken);
      options.selectedQueryLog.value = response.data;
      options.queryLogDetailModalOpen.value = true;
      options.modelCallSearchForm.traceId = response.data.trace_id;
      options.modelCallSearchForm.requestId = "";
      options.modelCallSearchForm.model = "";
      options.modelCallSearchForm.modelType = "";
      options.modelCallSearchForm.caller = "";
      options.modelCallSearchForm.status = "";
      options.modelCallSearchForm.degraded = "";
      options.modelCallSearchForm.errorCode = "";
      options.modelCallLogPagination.page = 1;
      await refreshModelCallLogs(accessToken);
    } catch (error) {
      options.selectedQueryLog.value = null;
      options.queryLogDetailModalOpen.value = false;
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取查询日志详情失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingQueryDetail = false;
    }
  }

  function closeQueryLogDetailModal(): void {
    options.queryLogDetailModalOpen.value = false;
  }

  async function openModelCallLogDetail(log: ModelCallLogListItemData): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }
    options.diagnosticsBusy.loadingModelCallDetail = true;
    try {
      const response = await getModelCallLog(log.id, accessToken);
      options.selectedModelCallLog.value = response.data;
      options.modelCallLogDetailModalOpen.value = true;
      options.diagnosticsFeedback.value = null;
    } catch (error) {
      options.selectedModelCallLog.value = null;
      options.modelCallLogDetailModalOpen.value = false;
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取模型调用详情失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingModelCallDetail = false;
    }
  }

  function closeModelCallLogDetailModal(): void {
    options.modelCallLogDetailModalOpen.value = false;
  }

  return {
    closeModelCallLogDetailModal,
    closeQueryLogDetailModal,
    openModelCallLogDetail,
    refreshModelCallLogs,
    refreshQueryLogs,
    selectQueryLog,
  };
}
