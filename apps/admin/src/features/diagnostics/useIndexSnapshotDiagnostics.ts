import {
  createAdminIndexCollectionRebuildJob,
  createAdminIndexCollectionSnapshot,
  listAdminIndexCollectionSnapshots,
  recoverAdminIndexCollectionSnapshot,
} from "@/api/indexOps";
import type { UseIndexDiagnosticsOptions } from "@/features/diagnostics/indexDiagnosticsTypes";

export function useIndexSnapshotDiagnostics(
  options: UseIndexDiagnosticsOptions,
  refreshIndexHealth: (existingAccessToken?: string) => Promise<void>,
) {
  async function refreshIndexCollectionSnapshots(existingAccessToken?: string): Promise<void> {
    if (
      !options.canLoadIndexOps.value ||
      !options.indexCollectionOpsForm.selectedCollectionName
    ) {
      options.indexCollectionSnapshots.value = [];
      options.clearPaginationState(options.indexSnapshotPagination);
      return;
    }
    const accessToken = existingAccessToken ?? (await options.ensureAccessToken());
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.loadingIndexSnapshots = true;
    try {
      const response = await listAdminIndexCollectionSnapshots(
        options.indexCollectionOpsForm.selectedCollectionName,
        accessToken,
        {
          page: options.indexSnapshotPagination.page,
          page_size: options.indexSnapshotPagination.pageSize,
        },
      );
      options.indexCollectionSnapshots.value = response.data;
      options.syncPaginationState(options.indexSnapshotPagination, response.pagination);
      if (
        options.indexCollectionSnapshots.value.length === 0 &&
        options.indexSnapshotPagination.total > 0 &&
        options.indexSnapshotPagination.page > 1
      ) {
        options.indexSnapshotPagination.page = options.paginationTotalPages(
          options.indexSnapshotPagination,
        );
        await refreshIndexCollectionSnapshots(accessToken);
        return;
      }
      options.diagnosticsFeedback.value = null;
    } catch (error) {
      options.indexCollectionSnapshots.value = [];
      options.clearPaginationState(options.indexSnapshotPagination);
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "读取 collection 快照失败"),
      };
    } finally {
      options.diagnosticsBusy.loadingIndexSnapshots = false;
    }
  }

  async function onIndexCollectionSelectionChange(): Promise<void> {
    options.indexCollectionOpsForm.confirmedSnapshot = false;
    options.indexCollectionOpsForm.confirmedRestore = false;
    options.indexCollectionOpsForm.confirmedRebuild = false;
    options.clearPaginationState(options.indexSnapshotPagination);
    await refreshIndexCollectionSnapshots();
  }

  async function createSelectedIndexCollectionSnapshot(): Promise<void> {
    if (!options.canCreateIndexCollectionSnapshot.value) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: "创建快照前必须选择 collection，并勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.creatingIndexSnapshot = true;
    try {
      const response = await createAdminIndexCollectionSnapshot(
        options.indexCollectionOpsForm.selectedCollectionName,
        accessToken,
        true,
      );
      options.indexCollectionOpsForm.confirmedSnapshot = false;
      options.indexSnapshotPagination.page = 1;
      await refreshIndexCollectionSnapshots(accessToken);
      options.diagnosticsFeedback.value = {
        tone: "success",
        message: `Qdrant 快照已创建：${response.data.name}`,
      };
    } catch (error) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "创建 Qdrant 快照失败"),
      };
    } finally {
      options.diagnosticsBusy.creatingIndexSnapshot = false;
    }
  }

  async function recoverSelectedIndexCollectionSnapshot(): Promise<void> {
    if (!options.canRecoverIndexCollectionSnapshot.value) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: "恢复快照前必须填写 snapshot URL 或 file URI，并勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.recoveringIndexSnapshot = true;
    try {
      const response = await recoverAdminIndexCollectionSnapshot(
        options.indexCollectionOpsForm.selectedCollectionName,
        {
          location: options.indexCollectionOpsForm.snapshotLocation.trim(),
          priority: options.indexCollectionOpsForm.recoverPriority,
          checksum: options.indexCollectionOpsForm.snapshotChecksum.trim() || null,
        },
        accessToken,
        true,
      );
      options.indexCollectionOpsForm.confirmedRestore = false;
      await refreshIndexHealth(accessToken);
      options.diagnosticsFeedback.value = {
        tone: "success",
        message: `Qdrant 快照恢复已提交：${response.data.result === false ? "未完成" : "已接受"}`,
      };
    } catch (error) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "恢复 Qdrant 快照失败"),
      };
    } finally {
      options.diagnosticsBusy.recoveringIndexSnapshot = false;
    }
  }

  async function rebuildSelectedIndexCollection(): Promise<void> {
    if (!options.canRebuildIndexCollection.value) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: "重建 collection 索引前必须选择 collection，并勾选确认项。",
      };
      return;
    }
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      return;
    }

    options.diagnosticsBusy.rebuildingIndexCollection = true;
    try {
      const response = await createAdminIndexCollectionRebuildJob(
        options.indexCollectionOpsForm.selectedCollectionName,
        accessToken,
        true,
      );
      options.indexCollectionOpsForm.confirmedRebuild = false;
      await refreshIndexHealth(accessToken);
      options.diagnosticsFeedback.value = {
        tone: "success",
        message: `Collection 重建索引任务已创建：${response.data.job_id ?? "-"}`,
      };
    } catch (error) {
      options.diagnosticsFeedback.value = {
        tone: "error",
        message: options.normalizeErrorMessage(error, "创建 collection 重建索引任务失败"),
      };
    } finally {
      options.diagnosticsBusy.rebuildingIndexCollection = false;
    }
  }

  return {
    createSelectedIndexCollectionSnapshot,
    onIndexCollectionSelectionChange,
    rebuildSelectedIndexCollection,
    recoverSelectedIndexCollectionSnapshot,
    refreshIndexCollectionSnapshots,
  };
}
