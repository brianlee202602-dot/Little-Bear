import type { ComputedRef, Ref } from "vue";

import type { PaginationData } from "@/api/commonTypes";
import type {
  IndexCollectionHealthData,
  IndexCollectionSnapshotData,
} from "@/api/indexOps";
import type { DiagnosticsPaginationState } from "@/features/diagnostics/useDiagnostics";

export interface UseIndexDiagnosticsOptions {
  canCreateIndexCollectionSnapshot: ComputedRef<boolean>;
  canLoadIndexOps: { readonly value: boolean };
  canRebuildIndexCollection: ComputedRef<boolean>;
  canRecoverIndexCollectionSnapshot: ComputedRef<boolean>;
  clearPaginationState: (state: DiagnosticsPaginationState) => void;
  diagnosticsBusy: {
    creatingIndexSnapshot: boolean;
    loadingIndexHealth: boolean;
    loadingIndexSnapshots: boolean;
    rebuildingIndexCollection: boolean;
    recoveringIndexSnapshot: boolean;
  };
  diagnosticsFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  ensureAccessToken: () => Promise<string | null>;
  indexCollectionOpsForm: {
    confirmedRebuild: boolean;
    confirmedRestore: boolean;
    confirmedSnapshot: boolean;
    recoverPriority: "Snapshot" | "Replica";
    selectedCollectionName: string;
    snapshotChecksum: string;
    snapshotLocation: string;
  };
  indexCollectionSnapshots: Ref<IndexCollectionSnapshotData[]>;
  indexHealth: Ref<IndexCollectionHealthData[]>;
  indexHealthPagination: DiagnosticsPaginationState;
  indexSnapshotPagination: DiagnosticsPaginationState;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  paginationTotalPages: (state: DiagnosticsPaginationState) => number;
  syncPaginationState: (
    state: DiagnosticsPaginationState,
    pagination: PaginationData,
  ) => void;
}
