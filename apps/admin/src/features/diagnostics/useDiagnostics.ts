import { computed, reactive, ref } from "vue";

import {
  type ModelCallLogData,
  type ModelCallLogListItemData,
  type QueryLogData,
  type QueryLogListItemData,
} from "@/api/diagnostics";
import type {
  IndexCollectionHealthData,
  IndexCollectionSnapshotData,
} from "@/api/indexOps";
import type { PaginationData } from "@/api/commonTypes";
import { useIndexDiagnostics } from "@/features/diagnostics/useIndexDiagnostics";
import { useLogDiagnostics } from "@/features/diagnostics/useLogDiagnostics";
import type { Tone } from "@/utils/status";

export type DiagnosticsPaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type UseDiagnosticsOptions = {
  canLoadDiagnostics: { value: boolean };
  canLoadIndexOps: { value: boolean };
  clearPaginationState: (state: DiagnosticsPaginationState) => void;
  ensureAccessToken: () => Promise<string | null>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  paginationTotalPages: (state: DiagnosticsPaginationState) => number;
  syncPaginationState: (state: DiagnosticsPaginationState, pagination: PaginationData) => void;
};

export function useDiagnostics(options: UseDiagnosticsOptions) {
  const {
    canLoadDiagnostics,
    canLoadIndexOps,
    clearPaginationState,
    ensureAccessToken,
    normalizeErrorMessage,
    paginationTotalPages,
    syncPaginationState,
  } = options;

  const diagnosticsBusy = reactive({
    loadingQueryLogs: false,
    loadingModelCallLogs: false,
    loadingQueryDetail: false,
    loadingModelCallDetail: false,
    loadingIndexHealth: false,
    loadingIndexSnapshots: false,
    creatingIndexSnapshot: false,
    recoveringIndexSnapshot: false,
    rebuildingIndexCollection: false,
  });
  const diagnosticsFeedback = ref<{ tone: Exclude<Tone, "warning">; message: string } | null>(
    null,
  );
  const queryLogSearchForm = reactive({
    userId: "",
    kbId: "",
    status: "",
    degraded: "",
    degradeReason: "",
    requestId: "",
    traceId: "",
    errorCode: "",
  });
  const modelCallSearchForm = reactive({
    model: "",
    modelType: "",
    caller: "",
    status: "",
    degraded: "",
    requestId: "",
    traceId: "",
    errorCode: "",
  });
  const indexCollectionOpsForm = reactive({
    selectedCollectionName: "",
    snapshotLocation: "",
    snapshotChecksum: "",
    recoverPriority: "Snapshot" as "Snapshot" | "Replica",
    confirmedSnapshot: false,
    confirmedRestore: false,
    confirmedRebuild: false,
  });
  const queryLogPagination = reactive<DiagnosticsPaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const modelCallLogPagination = reactive<DiagnosticsPaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const indexHealthPagination = reactive<DiagnosticsPaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const indexSnapshotPagination = reactive<DiagnosticsPaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const queryLogs = ref<QueryLogListItemData[]>([]);
  const modelCallLogs = ref<ModelCallLogListItemData[]>([]);
  const indexHealth = ref<IndexCollectionHealthData[]>([]);
  const indexCollectionSnapshots = ref<IndexCollectionSnapshotData[]>([]);
  const selectedQueryLog = ref<QueryLogData | null>(null);
  const selectedModelCallLog = ref<ModelCallLogData | null>(null);
  const queryLogDetailModalOpen = ref(false);
  const modelCallLogDetailModalOpen = ref(false);

  const selectedIndexCollectionHealth = computed(
    () =>
      indexHealth.value.find(
        (item) => item.collection_name === indexCollectionOpsForm.selectedCollectionName,
      ) ?? null,
  );
  const canCreateIndexCollectionSnapshot = computed(
    () =>
      canLoadIndexOps.value &&
      Boolean(selectedIndexCollectionHealth.value) &&
      indexCollectionOpsForm.confirmedSnapshot &&
      !diagnosticsBusy.creatingIndexSnapshot,
  );
  const canRecoverIndexCollectionSnapshot = computed(
    () =>
      canLoadIndexOps.value &&
      Boolean(selectedIndexCollectionHealth.value) &&
      indexCollectionOpsForm.snapshotLocation.trim().length > 0 &&
      indexCollectionOpsForm.confirmedRestore &&
      !diagnosticsBusy.recoveringIndexSnapshot,
  );
  const canRebuildIndexCollection = computed(
    () =>
      canLoadIndexOps.value &&
      Boolean(selectedIndexCollectionHealth.value) &&
      indexCollectionOpsForm.confirmedRebuild &&
      !diagnosticsBusy.rebuildingIndexCollection,
  );

  const {
    createSelectedIndexCollectionSnapshot,
    onIndexCollectionSelectionChange,
    rebuildSelectedIndexCollection,
    recoverSelectedIndexCollectionSnapshot,
    refreshIndexCollectionSnapshots,
    refreshIndexHealth,
  } = useIndexDiagnostics({
    canCreateIndexCollectionSnapshot,
    canLoadIndexOps,
    canRebuildIndexCollection,
    canRecoverIndexCollectionSnapshot,
    clearPaginationState,
    diagnosticsBusy,
    diagnosticsFeedback,
    ensureAccessToken,
    indexCollectionOpsForm,
    indexCollectionSnapshots,
    indexHealth,
    indexHealthPagination,
    indexSnapshotPagination,
    normalizeErrorMessage,
    paginationTotalPages,
    syncPaginationState,
  });
  const {
    closeModelCallLogDetailModal,
    closeQueryLogDetailModal,
    openModelCallLogDetail,
    refreshModelCallLogs,
    refreshQueryLogs,
    selectQueryLog,
  } = useLogDiagnostics({
    canLoadDiagnostics,
    clearPaginationState,
    diagnosticsBusy,
    diagnosticsFeedback,
    ensureAccessToken,
    modelCallLogDetailModalOpen,
    modelCallLogPagination,
    modelCallLogs,
    modelCallSearchForm,
    normalizeErrorMessage,
    queryLogDetailModalOpen,
    queryLogPagination,
    queryLogs,
    queryLogSearchForm,
    selectedModelCallLog,
    selectedQueryLog,
    syncPaginationState,
  });

  async function refreshDiagnosticsState(): Promise<void> {
    if (!canLoadDiagnostics.value && !canLoadIndexOps.value) {
      queryLogs.value = [];
      modelCallLogs.value = [];
      indexHealth.value = [];
      clearPaginationState(indexHealthPagination);
      indexCollectionSnapshots.value = [];
      clearPaginationState(indexSnapshotPagination);
      selectedQueryLog.value = null;
      diagnosticsFeedback.value = {
        tone: "error",
        message: "当前账号缺少 audit:read 和 document:index，无法查看查询诊断或索引运维。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    diagnosticsFeedback.value = null;
    const tasks: Promise<void>[] = [];
    if (canLoadDiagnostics.value) {
      tasks.push(refreshQueryLogs(accessToken), refreshModelCallLogs(accessToken));
    } else {
      queryLogs.value = [];
      modelCallLogs.value = [];
      selectedQueryLog.value = null;
      selectedModelCallLog.value = null;
      modelCallLogDetailModalOpen.value = false;
    }
    if (canLoadIndexOps.value) {
      tasks.push(refreshIndexHealth(accessToken));
    } else {
      indexHealth.value = [];
      clearPaginationState(indexHealthPagination);
      indexCollectionSnapshots.value = [];
      clearPaginationState(indexSnapshotPagination);
    }
    await Promise.all(tasks);
  }

  function resetDiagnosticsFilters(): void {
    queryLogSearchForm.userId = "";
    queryLogSearchForm.kbId = "";
    queryLogSearchForm.status = "";
    queryLogSearchForm.degraded = "";
    queryLogSearchForm.degradeReason = "";
    queryLogSearchForm.requestId = "";
    queryLogSearchForm.traceId = "";
    queryLogSearchForm.errorCode = "";
    modelCallSearchForm.model = "";
    modelCallSearchForm.modelType = "";
    modelCallSearchForm.caller = "";
    modelCallSearchForm.status = "";
    modelCallSearchForm.degraded = "";
    modelCallSearchForm.requestId = "";
    modelCallSearchForm.traceId = "";
    modelCallSearchForm.errorCode = "";
    queryLogPagination.page = 1;
    modelCallLogPagination.page = 1;
    queryLogDetailModalOpen.value = false;
    modelCallLogDetailModalOpen.value = false;
  }

  function clearDiagnosticsState(): void {
    queryLogs.value = [];
    modelCallLogs.value = [];
    indexHealth.value = [];
    clearPaginationState(indexHealthPagination);
    indexCollectionSnapshots.value = [];
    clearPaginationState(indexSnapshotPagination);
    selectedQueryLog.value = null;
    selectedModelCallLog.value = null;
    diagnosticsFeedback.value = null;
    resetDiagnosticsFilters();
    clearPaginationState(queryLogPagination);
    clearPaginationState(modelCallLogPagination);
    indexCollectionOpsForm.selectedCollectionName = "";
    indexCollectionOpsForm.snapshotLocation = "";
    indexCollectionOpsForm.snapshotChecksum = "";
    indexCollectionOpsForm.recoverPriority = "Snapshot";
    indexCollectionOpsForm.confirmedSnapshot = false;
    indexCollectionOpsForm.confirmedRestore = false;
    indexCollectionOpsForm.confirmedRebuild = false;
  }

  return {
    canCreateIndexCollectionSnapshot,
    canLoadDiagnostics,
    canLoadIndexOps,
    canRebuildIndexCollection,
    canRecoverIndexCollectionSnapshot,
    clearDiagnosticsState,
    closeModelCallLogDetailModal,
    closeQueryLogDetailModal,
    createSelectedIndexCollectionSnapshot,
    diagnosticsBusy,
    diagnosticsFeedback,
    indexCollectionOpsForm,
    indexCollectionSnapshots,
    indexHealth,
    indexHealthPagination,
    indexSnapshotPagination,
    modelCallLogDetailModalOpen,
    modelCallLogPagination,
    modelCallLogs,
    modelCallSearchForm,
    onIndexCollectionSelectionChange,
    openModelCallLogDetail,
    queryLogDetailModalOpen,
    queryLogPagination,
    queryLogs,
    queryLogSearchForm,
    rebuildSelectedIndexCollection,
    recoverSelectedIndexCollectionSnapshot,
    refreshDiagnosticsState,
    refreshIndexCollectionSnapshots,
    refreshIndexHealth,
    refreshModelCallLogs,
    refreshQueryLogs,
    resetDiagnosticsFilters,
    selectQueryLog,
    selectedIndexCollectionHealth,
    selectedModelCallLog,
    selectedQueryLog,
  };
}

export type DiagnosticsRuntime = ReturnType<typeof useDiagnostics>;
