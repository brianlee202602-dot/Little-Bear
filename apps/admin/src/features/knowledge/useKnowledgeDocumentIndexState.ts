import { computed, type ComputedRef } from "vue";

import type { AdminDocumentData, AdminDocumentListItemData } from "@/api/documents";

type DocumentIndexForm = {
  confirmedRebuild: boolean;
  confirmedBatchRebuild: boolean;
  confirmedCleanup: boolean;
};

type ImportBusyState = {
  rebuildingIndex: boolean;
  rebuildingBatchIndex: boolean;
  cleaningIndexVersions: boolean;
};

export function isDocumentBatchRebuildEligible(
  document: AdminDocumentData | AdminDocumentListItemData,
): boolean {
  if ("can_rebuild_index" in document) {
    return document.can_rebuild_index;
  }
  return document.lifecycle_status === "active" && Boolean(document.current_version_id);
}

export function useKnowledgeDocumentIndexState(options: {
  canIndexDocuments: ComputedRef<boolean>;
  documentIndexForm: DocumentIndexForm;
  importAdminBusy: ImportBusyState;
  selectedAdminDocument: ComputedRef<AdminDocumentData | null>;
  selectedBatchRebuildDocumentIds: ComputedRef<string[]>;
  selectedCleanupPendingDeleteIndexVersionIds: ComputedRef<string[]>;
}) {
  const canRebuildSelectedDocumentIndex = computed(
    () =>
      options.canIndexDocuments.value &&
      options.selectedAdminDocument.value?.lifecycle_status === "active" &&
      Boolean(options.selectedAdminDocument.value?.current_version_id) &&
      options.documentIndexForm.confirmedRebuild &&
      !options.importAdminBusy.rebuildingIndex,
  );
  const canRebuildSelectedDocumentsIndex = computed(
    () =>
      options.canIndexDocuments.value &&
      options.selectedBatchRebuildDocumentIds.value.length > 0 &&
      options.documentIndexForm.confirmedBatchRebuild &&
      !options.importAdminBusy.rebuildingBatchIndex,
  );
  const canCleanupSelectedIndexVersions = computed(
    () =>
      options.canIndexDocuments.value &&
      options.selectedCleanupPendingDeleteIndexVersionIds.value.length > 0 &&
      options.documentIndexForm.confirmedCleanup &&
      !options.importAdminBusy.cleaningIndexVersions,
  );

  return {
    canCleanupSelectedIndexVersions,
    canRebuildSelectedDocumentIndex,
    canRebuildSelectedDocumentsIndex,
    isDocumentBatchRebuildEligible,
  };
}
