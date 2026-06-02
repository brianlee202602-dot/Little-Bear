import { computed, type Ref } from "vue";

import type { AdminDocumentData, AdminDocumentListItemData } from "@/api/documents";
import type { AdminFolderData, AdminFolderOptionData } from "@/api/folders";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";

export function useKnowledgeDerivedState(options: {
  adminDocuments: Ref<AdminDocumentListItemData[]>;
  adminFolderOptions: Ref<AdminFolderOptionData[]>;
  adminFolders: Ref<AdminFolderData[]>;
  adminKnowledgeBaseOptions: Ref<AdminKnowledgeBaseOptionData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  importUploadForm: { kbId: string };
  selectedAdminDocumentDetail: Ref<AdminDocumentData | null>;
  selectedDocumentId: Ref<string>;
  selectedFolderId: Ref<string>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
  selectedKnowledgeBaseId: Ref<string>;
}) {
  const activeKnowledgeBases = computed(() =>
    options.adminKnowledgeBaseOptions.value.filter(
      (knowledgeBase) => knowledgeBase.status === "active",
    ),
  );
  const selectedKnowledgeBase = computed(
    () =>
      options.selectedKnowledgeBaseDetail.value?.id === options.selectedKnowledgeBaseId.value
        ? options.selectedKnowledgeBaseDetail.value
        : (options.adminKnowledgeBases.value.find(
            (knowledgeBase) => knowledgeBase.id === options.selectedKnowledgeBaseId.value,
          ) ?? null),
  );
  const selectedFolder = computed(
    () =>
      options.adminFolders.value.find(
        (folder) => folder.id === options.selectedFolderId.value,
      ) ?? null,
  );
  const selectedAdminDocumentListItem = computed(
    () =>
      options.adminDocuments.value.find(
        (document) => document.id === options.selectedDocumentId.value,
      ) ?? null,
  );
  const selectedAdminDocument = computed(() =>
    options.selectedAdminDocumentDetail.value?.id === options.selectedDocumentId.value
      ? options.selectedAdminDocumentDetail.value
      : null,
  );
  const selectedDocumentForDisplay = computed(
    () => selectedAdminDocument.value ?? selectedAdminDocumentListItem.value,
  );
  const activeFolders = computed(() =>
    options.adminFolderOptions.value.filter((folder) => folder.status === "active"),
  );
  const folderParentOptions = computed(() =>
    activeFolders.value.filter((folder) => folder.id !== options.selectedFolderId.value),
  );
  const selectedImportKnowledgeBase = computed(
    () =>
      options.selectedKnowledgeBaseDetail.value?.id === options.importUploadForm.kbId
        ? options.selectedKnowledgeBaseDetail.value
        : (options.adminKnowledgeBases.value.find(
            (knowledgeBase) => knowledgeBase.id === options.importUploadForm.kbId,
          ) ?? null),
  );

  return {
    activeFolders,
    activeKnowledgeBases,
    folderParentOptions,
    selectedAdminDocument,
    selectedDocumentForDisplay,
    selectedFolder,
    selectedImportKnowledgeBase,
    selectedKnowledgeBase,
  };
}
