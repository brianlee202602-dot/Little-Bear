import type { ComputedRef, Ref } from "vue";

import type { AdminFolderOptionData } from "@/api/folders";
import type { ImportJobData, ImportJobListItemData, ImportJobResponse } from "@/api/imports";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";
import type { KnowledgeBaseModalMode } from "@/features/knowledge/useKnowledgeModals";

export interface UseKnowledgeBaseUploadDependencies {
  activeFolders: ComputedRef<AdminFolderOptionData[]>;
  activeKnowledgeBases: ComputedRef<AdminKnowledgeBaseOptionData[]>;
  adminImportJobs: Ref<ImportJobListItemData[]>;
  canImportDocuments: ComputedRef<boolean>;
  canReadImportJobs: ComputedRef<boolean>;
  canUploadImportFiles: ComputedRef<boolean>;
  closeKnowledgeBaseModal: () => void;
  ensureAccessToken: () => Promise<string | null>;
  importAdminBusy: {
    uploading: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importFileInputKey: Ref<number>;
  importJobListItemFromDetail: (job: ImportJobData) => ImportJobListItemData;
  importUploadForm: {
    folderId: string;
    idempotencyKey: string;
    kbId: string;
    visibility: "department" | "enterprise";
  };
  importUploadPermissionParentConflict: ComputedRef<string>;
  knowledgeBaseModalMode: Ref<KnowledgeBaseModalMode>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  refreshKnowledgeBaseAdminState: () => Promise<void>;
  selectKnowledgeBase: (knowledgeBaseId: string) => Promise<void>;
  selectedFolderId: Ref<string>;
  selectedImportFiles: Ref<File[]>;
  selectedImportKnowledgeBase: ComputedRef<
    AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null
  >;
  uploadKnowledgeBaseDocuments: (
    knowledgeBaseId: string,
    payload: {
      files: File[];
      folder_id?: string;
      idempotency_key?: string;
      owner_department_id?: string;
      visibility: "department" | "enterprise";
    },
    accessToken: string,
  ) => Promise<ImportJobResponse>;
}

export function useKnowledgeBaseUpload(options: UseKnowledgeBaseUploadDependencies) {
  const {
    activeFolders,
    activeKnowledgeBases,
    adminImportJobs,
    canImportDocuments,
    canReadImportJobs,
    canUploadImportFiles,
    closeKnowledgeBaseModal,
    ensureAccessToken,
    importAdminBusy,
    importAdminFeedback,
    importFileInputKey,
    importJobListItemFromDetail,
    importUploadForm,
    importUploadPermissionParentConflict,
    knowledgeBaseModalMode,
    normalizeErrorMessage,
    refreshKnowledgeBaseAdminState,
    selectKnowledgeBase,
    selectedFolderId,
    selectedImportFiles,
    selectedImportKnowledgeBase,
    uploadKnowledgeBaseDocuments,
  } = options;

  async function openUploadKnowledgeBaseModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    await selectKnowledgeBase(knowledgeBase.id);
    knowledgeBaseModalMode.value = "upload";
    importUploadForm.kbId = knowledgeBase.id;
    importUploadForm.folderId =
      selectedFolderId.value &&
      activeFolders.value.some((folder) => folder.id === selectedFolderId.value)
        ? selectedFolderId.value
        : "";
    importUploadForm.visibility = knowledgeBase.default_document_visibility;
    importUploadForm.idempotencyKey = "";
    clearImportFiles();
  }

  function ensureImportKnowledgeBaseSelection(): void {
    if (
      importUploadForm.kbId &&
      activeKnowledgeBases.value.some(
        (knowledgeBase) => knowledgeBase.id === importUploadForm.kbId,
      )
    ) {
      return;
    }
    importUploadForm.kbId = activeKnowledgeBases.value[0]?.id ?? importUploadForm.kbId;
  }

  function onImportFilesChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    selectedImportFiles.value = Array.from(input.files ?? []);
  }

  function clearImportFiles(): void {
    selectedImportFiles.value = [];
    importFileInputKey.value += 1;
  }

  async function submitDocumentUpload(): Promise<void> {
    if (importUploadPermissionParentConflict.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: importUploadPermissionParentConflict.value,
      };
      return;
    }
    if (!canUploadImportFiles.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: !canImportDocuments.value
          ? "当前账号缺少 document:import，不能上传文档。"
          : "请选择目标知识库和至少一个文件。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.uploading = true;
    try {
      const response = await uploadKnowledgeBaseDocuments(
        importUploadForm.kbId.trim(),
        {
          files: selectedImportFiles.value,
          visibility: importUploadForm.visibility,
          owner_department_id:
            selectedImportKnowledgeBase.value?.default_document_owner_department_id,
          folder_id: importUploadForm.folderId || undefined,
          idempotency_key: importUploadForm.idempotencyKey.trim() || undefined,
        },
        accessToken,
      );
      const listItem = importJobListItemFromDetail(response.data);
      adminImportJobs.value = [
        listItem,
        ...adminImportJobs.value.filter((job) => job.id !== listItem.id),
      ];
      clearImportFiles();
      importUploadForm.idempotencyKey = "";
      if (canReadImportJobs.value) {
        await refreshKnowledgeBaseAdminState();
      }
      importAdminFeedback.value = {
        tone: "success",
        message: `上传任务已创建：${response.data.id}`,
      };
      closeKnowledgeBaseModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "上传文档失败"),
      };
    } finally {
      importAdminBusy.uploading = false;
    }
  }

  return {
    clearImportFiles,
    ensureImportKnowledgeBaseSelection,
    onImportFilesChange,
    openUploadKnowledgeBaseModal,
    submitDocumentUpload,
  };
}
