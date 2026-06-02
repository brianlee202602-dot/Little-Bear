import { reactive, ref } from "vue";

import { listAuditLogs, type AuditLogListItemData } from "@/api/audit";
import type { PaginationData } from "@/api/commonTypes";
import type { Tone } from "@/utils/status";

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type UseAuditLogsOptions = {
  canReadAudit: { value: boolean };
  clearPaginationState: (state: PaginationState) => void;
  ensureAccessToken: () => Promise<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  syncPaginationState: (state: PaginationState, pagination: PaginationData) => void;
};

export function useAuditLogs(options: UseAuditLogsOptions) {
  const {
    canReadAudit,
    clearPaginationState,
    ensureAccessToken,
    normalizeErrorMessage,
    syncPaginationState,
  } = options;

  const auditFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(null);
  const auditLogs = ref<AuditLogListItemData[]>([]);
  const auditLogPagination = reactive<PaginationState>({ page: 1, pageSize: 20, total: 0 });

  async function refreshConfigAuditLogs(): Promise<void> {
    if (!canReadAudit.value) {
      auditLogs.value = [];
      clearPaginationState(auditLogPagination);
      auditFeedback.value = null;
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }
    try {
      const auditResponse = await listAuditLogs(accessToken, {
        page: auditLogPagination.page,
        page_size: auditLogPagination.pageSize,
        resource_type: "config",
      });
      auditLogs.value = auditResponse.data;
      syncPaginationState(auditLogPagination, auditResponse.pagination);
      auditFeedback.value = null;
    } catch (error) {
      auditLogs.value = [];
      clearPaginationState(auditLogPagination);
      auditFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取配置审计日志失败"),
      };
    }
  }

  function clearAuditLogsState(): void {
    auditLogs.value = [];
    auditFeedback.value = null;
    clearPaginationState(auditLogPagination);
  }

  return {
    auditFeedback,
    auditLogPagination,
    auditLogs,
    clearAuditLogsState,
    refreshConfigAuditLogs,
  };
}

export type AuditLogsRuntime = ReturnType<typeof useAuditLogs>;
