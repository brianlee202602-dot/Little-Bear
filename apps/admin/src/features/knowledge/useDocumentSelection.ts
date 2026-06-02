import { computed, ref, type Ref } from "vue";

import type {
  AdminDocumentData,
  AdminDocumentListItemData,
  ChunkData,
  DocumentVersionData,
  IndexVersionData,
} from "@/api/documents";

type PaginationState = {
  page: number;
  pageSize: number;
  total: number;
};

type DocumentIndexForm = {
  confirmedRebuild: boolean;
  confirmedBatchRebuild: boolean;
  confirmedCleanup: boolean;
};

export function useDocumentSelection(options: {
  adminDocuments: Ref<AdminDocumentListItemData[]>;
  clearPaginationState: (state: PaginationState) => void;
  documentChunkPagination: PaginationState;
  documentIndexForm: DocumentIndexForm;
  documentIndexVersionPagination: PaginationState;
  documentVersionPagination: PaginationState;
  isDocumentBatchRebuildEligible: (
    document: AdminDocumentData | AdminDocumentListItemData,
  ) => boolean;
}) {
  const selectedAdminDocumentDetail = ref<AdminDocumentData | null>(null);
  const selectedDocumentVersions = ref<DocumentVersionData[]>([]);
  const selectedDocumentIndexVersions = ref<IndexVersionData[]>([]);
  const selectedDocumentChunks = ref<ChunkData[]>([]);
  const highlightedDocumentChunkId = ref("");
  const selectedBatchDocumentIds = ref<string[]>([]);
  const selectedCleanupIndexVersionIds = ref<string[]>([]);

  const batchRebuildEligibleDocuments = computed(() =>
    options.adminDocuments.value.filter((document) =>
      options.isDocumentBatchRebuildEligible(document),
    ),
  );
  const selectedBatchDocumentSet = computed(() => new Set(selectedBatchDocumentIds.value));
  const selectedBatchRebuildDocumentIds = computed(() => {
    const eligibleIds = new Set(batchRebuildEligibleDocuments.value.map((document) => document.id));
    return selectedBatchDocumentIds.value.filter((documentId) => eligibleIds.has(documentId));
  });
  const allBatchRebuildEligibleDocumentsSelected = computed(
    () =>
      batchRebuildEligibleDocuments.value.length > 0 &&
      selectedBatchRebuildDocumentIds.value.length === batchRebuildEligibleDocuments.value.length,
  );
  const cleanupEligibleIndexVersions = computed(() =>
    selectedDocumentIndexVersions.value.filter((version) => version.status === "pending_delete"),
  );
  const selectedCleanupIndexVersionSet = computed(
    () => new Set(selectedCleanupIndexVersionIds.value),
  );
  const selectedCleanupPendingDeleteIndexVersionIds = computed(() => {
    const eligibleIds = new Set(cleanupEligibleIndexVersions.value.map((version) => version.id));
    return selectedCleanupIndexVersionIds.value.filter((indexVersionId) =>
      eligibleIds.has(indexVersionId),
    );
  });
  const allCleanupEligibleIndexVersionsSelected = computed(
    () =>
      cleanupEligibleIndexVersions.value.length > 0 &&
      selectedCleanupPendingDeleteIndexVersionIds.value.length ===
        cleanupEligibleIndexVersions.value.length,
  );

  function clearSelectedDocumentDetails(): void {
    selectedDocumentVersions.value = [];
    selectedDocumentIndexVersions.value = [];
    selectedDocumentChunks.value = [];
    highlightedDocumentChunkId.value = "";
    options.clearPaginationState(options.documentVersionPagination);
    options.clearPaginationState(options.documentIndexVersionPagination);
    options.clearPaginationState(options.documentChunkPagination);
    options.documentIndexForm.confirmedRebuild = false;
    clearIndexVersionCleanupSelection();
  }

  function clearBatchDocumentSelection(): void {
    selectedBatchDocumentIds.value = [];
    options.documentIndexForm.confirmedBatchRebuild = false;
  }

  function clearIndexVersionCleanupSelection(): void {
    selectedCleanupIndexVersionIds.value = [];
    options.documentIndexForm.confirmedCleanup = false;
  }

  function pruneSelectedBatchDocuments(): void {
    const visibleEligibleIds = new Set(
      options.adminDocuments.value
        .filter((document) => options.isDocumentBatchRebuildEligible(document))
        .map((document) => document.id),
    );
    selectedBatchDocumentIds.value = selectedBatchDocumentIds.value.filter((documentId) =>
      visibleEligibleIds.has(documentId),
    );
    if (selectedBatchDocumentIds.value.length === 0) {
      options.documentIndexForm.confirmedBatchRebuild = false;
    }
  }

  function toggleBatchDocumentSelection(documentId: string, checked: boolean): void {
    const next = new Set(selectedBatchDocumentIds.value);
    if (checked) {
      next.add(documentId);
    } else {
      next.delete(documentId);
    }
    selectedBatchDocumentIds.value = Array.from(next);
    if (selectedBatchDocumentIds.value.length === 0) {
      options.documentIndexForm.confirmedBatchRebuild = false;
    }
  }

  function onBatchDocumentSelectionToggle(documentId: string, event: Event): void {
    toggleBatchDocumentSelection(documentId, (event.target as HTMLInputElement).checked);
  }

  function toggleAllBatchDocuments(checked: boolean): void {
    selectedBatchDocumentIds.value = checked
      ? batchRebuildEligibleDocuments.value.map((document) => document.id)
      : [];
    if (!checked) {
      options.documentIndexForm.confirmedBatchRebuild = false;
    }
  }

  function onAllBatchDocumentsToggle(event: Event): void {
    toggleAllBatchDocuments((event.target as HTMLInputElement).checked);
  }

  function pruneSelectedIndexVersionsForCleanup(): void {
    const eligibleIds = new Set(cleanupEligibleIndexVersions.value.map((version) => version.id));
    selectedCleanupIndexVersionIds.value = selectedCleanupIndexVersionIds.value.filter(
      (indexVersionId) => eligibleIds.has(indexVersionId),
    );
    if (selectedCleanupIndexVersionIds.value.length === 0) {
      options.documentIndexForm.confirmedCleanup = false;
    }
  }

  function toggleIndexVersionCleanupSelection(indexVersionId: string, checked: boolean): void {
    const next = new Set(selectedCleanupIndexVersionIds.value);
    if (checked) {
      next.add(indexVersionId);
    } else {
      next.delete(indexVersionId);
    }
    selectedCleanupIndexVersionIds.value = Array.from(next);
    if (selectedCleanupIndexVersionIds.value.length === 0) {
      options.documentIndexForm.confirmedCleanup = false;
    }
  }

  function onIndexVersionCleanupSelectionToggle(indexVersionId: string, event: Event): void {
    toggleIndexVersionCleanupSelection(
      indexVersionId,
      (event.target as HTMLInputElement).checked,
    );
  }

  function toggleAllIndexVersionsForCleanup(checked: boolean): void {
    selectedCleanupIndexVersionIds.value = checked
      ? cleanupEligibleIndexVersions.value.map((version) => version.id)
      : [];
    if (!checked) {
      options.documentIndexForm.confirmedCleanup = false;
    }
  }

  function onAllIndexVersionsForCleanupToggle(event: Event): void {
    toggleAllIndexVersionsForCleanup((event.target as HTMLInputElement).checked);
  }

  function selectDocumentChunk(chunkId: string): void {
    highlightedDocumentChunkId.value = chunkId;
  }

  return {
    allBatchRebuildEligibleDocumentsSelected,
    allCleanupEligibleIndexVersionsSelected,
    batchRebuildEligibleDocuments,
    cleanupEligibleIndexVersions,
    clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection,
    clearSelectedDocumentDetails,
    highlightedDocumentChunkId,
    onAllBatchDocumentsToggle,
    onAllIndexVersionsForCleanupToggle,
    onBatchDocumentSelectionToggle,
    onIndexVersionCleanupSelectionToggle,
    pruneSelectedBatchDocuments,
    pruneSelectedIndexVersionsForCleanup,
    selectDocumentChunk,
    selectedAdminDocumentDetail,
    selectedBatchDocumentIds,
    selectedBatchDocumentSet,
    selectedBatchRebuildDocumentIds,
    selectedCleanupIndexVersionIds,
    selectedCleanupIndexVersionSet,
    selectedCleanupPendingDeleteIndexVersionIds,
    selectedDocumentChunks,
    selectedDocumentIndexVersions,
    selectedDocumentVersions,
  };
}
