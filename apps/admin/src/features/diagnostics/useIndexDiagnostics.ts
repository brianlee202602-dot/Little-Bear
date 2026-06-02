import { getAdminIndexHealth } from "@/api/indexOps";
import type { UseIndexDiagnosticsOptions } from "@/features/diagnostics/indexDiagnosticsTypes";
import { useIndexSnapshotDiagnostics } from "@/features/diagnostics/useIndexSnapshotDiagnostics";

export function useIndexDiagnostics(options: UseIndexDiagnosticsOptions) {
  function syncIndexCollectionSelection(): void {
    const selected = options.indexCollectionOpsForm.selectedCollectionName;
    if (
      selected &&
      options.indexHealth.value.some((item) => item.collection_name === selected)
    ) {
      return;
    }
    options.indexCollectionOpsForm.selectedCollectionName =
      options.indexHealth.value[0]?.collection_name ?? "";
    options.clearPaginationState(options.indexSnapshotPagination);
    options.indexCollectionOpsForm.confirmedSnapshot = false;
    options.indexCollectionOpsForm.confirmedRestore = false;
    options.indexCollectionOpsForm.confirmedRebuild = false;
  }

  async function refreshIndexHealth(existingAccessToken?: string): Promise<void> {
    if (!options.canLoadIndexOps.value) {
      options.indexHealth.value = [];
      options.clearPaginationState(options.indexHealthPagination);
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.loadingIndexHealth = true;
    try {
      const response = await getAdminIndexHealth(accessToken, {
        page: options.indexHealthPagination.page,
        page_size: options.indexHealthPagination.pageSize,
      });
      options.indexHealth.value = response.data;
      options.syncPaginationState(options.indexHealthPagination, response.pagination);
      if (
        options.indexHealth.value.length === 0 &&
        options.indexHealthPagination.total > 0 &&
        options.indexHealthPagination.page > 1
      ) {
        options.indexHealthPagination.page = options.paginationTotalPages(
          options.indexHealthPagination,
        );
        await refreshIndexHealth(accessToken);
        return;
      }
      options.diagnosticsFeedback.value = null;
      syncIndexCollectionSelection();
      if (options.indexCollectionOpsForm.selectedCollectionName) {
        await refreshIndexCollectionSnapshots(accessToken);
      } else {
        options.indexCollectionSnapshots.value = [];
        options.clearPaginationState(options.indexSnapshotPagination);
      }
    } catch (error) {
      options.indexHealth.value = [];
      options.clearPaginationState(options.indexHealthPagination);
      options.indexCollectionSnapshots.value = [];
      options.clearPaginationState(options.indexSnapshotPagination);
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取索引运维诊断失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingIndexHealth = false;
    }
  }

  const {
    createSelectedIndexCollectionSnapshot,
    onIndexCollectionSelectionChange,
    rebuildSelectedIndexCollection,
    recoverSelectedIndexCollectionSnapshot,
    refreshIndexCollectionSnapshots,
  } = useIndexSnapshotDiagnostics(options, refreshIndexHealth);

  return {
    createSelectedIndexCollectionSnapshot,
    onIndexCollectionSelectionChange,
    rebuildSelectedIndexCollection,
    recoverSelectedIndexCollectionSnapshot,
    refreshIndexCollectionSnapshots,
    refreshIndexHealth,
  };
}
