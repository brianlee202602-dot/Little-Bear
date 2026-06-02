import type { ComputedRef, Ref } from "vue";

import type {
  AcceptedResponse,
  AdminFolderCreateRequest,
  AdminFolderData,
  AdminFolderListResponse,
  AdminFolderOptionData,
  AdminFolderPatchRequest,
  AdminFolderResponse,
} from "@/api/folders";
import type { AdminKnowledgeBaseData } from "@/api/knowledgeBases";
import type { FolderModalMode } from "@/features/knowledge/useKnowledgeModals";
import type { PaginationState } from "@/utils/pagination";

export interface UseKnowledgeFoldersDependencies {
  activeFolders: ComputedRef<AdminFolderOptionData[]>;
  adminFolderOptions: Ref<AdminFolderOptionData[]>;
  adminFolders: Ref<AdminFolderData[]>;
  canCreateFolder: ComputedRef<boolean>;
  canManageFolders: ComputedRef<boolean>;
  canUpdateSelectedFolder: ComputedRef<boolean>;
  clearPaginationState: (state: PaginationState) => void;
  createAdminFolder: (
    kbId: string,
    payload: AdminFolderCreateRequest,
    accessToken: string,
  ) => Promise<AdminFolderResponse>;
  deleteAdminFolder: (
    folderId: string,
    accessToken: string,
    confirmed: boolean,
  ) => Promise<AcceptedResponse>;
  ensureAccessToken: () => Promise<string | null>;
  folderCreateForm: {
    name: string;
    parentId: string;
  };
  folderDangerForm: {
    confirmedDelete: boolean;
  };
  folderEditForm: {
    name: string;
    parentId: string;
    status: "active" | "disabled" | "archived";
  };
  folderModalMode: Ref<FolderModalMode>;
  folderPagination: PaginationState;
  importAdminBusy: {
    loadingFolders: boolean;
    managingFolder: boolean;
  };
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  importUploadForm: {
    folderId: string;
  };
  listAdminFolders: (
    kbId: string,
    accessToken: string,
    filters: { page?: number; page_size?: number },
  ) => Promise<AdminFolderListResponse>;
  normalizeErrorMessage: (error: unknown, fallback: string) => string;
  paginationTotalPages: (state: PaginationState) => number;
  patchAdminFolder: (
    folderId: string,
    payload: AdminFolderPatchRequest,
    accessToken: string,
  ) => Promise<AdminFolderResponse>;
  refreshFolderOptions: (existingAccessToken?: string) => Promise<void>;
  refreshSelectedKnowledgeBaseDocuments: (existingAccessToken?: string) => Promise<void>;
  selectedFolder: ComputedRef<AdminFolderData | null>;
  selectedFolderId: Ref<string>;
  selectedKnowledgeBase: ComputedRef<AdminKnowledgeBaseData | { id: string } | null>;
  syncFolderEditForm: () => void;
  syncPaginationState: (
    state: PaginationState,
    pagination: { page: number; page_size: number; total: number },
  ) => void;
}

export function useKnowledgeFolders(options: UseKnowledgeFoldersDependencies) {
  const {
    activeFolders,
    adminFolderOptions,
    adminFolders,
    canCreateFolder,
    canManageFolders,
    canUpdateSelectedFolder,
    clearPaginationState,
    createAdminFolder,
    deleteAdminFolder,
    ensureAccessToken,
    folderCreateForm,
    folderDangerForm,
    folderEditForm,
    folderModalMode,
    folderPagination,
    importAdminBusy,
    importAdminFeedback,
    importUploadForm,
    listAdminFolders,
    normalizeErrorMessage,
    paginationTotalPages,
    patchAdminFolder,
    refreshFolderOptions,
    refreshSelectedKnowledgeBaseDocuments,
    selectedFolder,
    selectedFolderId,
    selectedKnowledgeBase,
    syncFolderEditForm,
    syncPaginationState,
  } = options;

  async function refreshSelectedKnowledgeBaseFolders(existingAccessToken?: string): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canManageFolders.value) {
      adminFolders.value = [];
      adminFolderOptions.value = [];
      clearPaginationState(folderPagination);
      selectedFolderId.value = "";
      importUploadForm.folderId = "";
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingFolders = true;
    try {
      const foldersResponse = await listAdminFolders(knowledgeBase.id, accessToken, {
        page: folderPagination.page,
        page_size: folderPagination.pageSize,
      });
      adminFolders.value = foldersResponse.data;
      syncPaginationState(folderPagination, foldersResponse.pagination);
      if (
        adminFolders.value.length === 0 &&
        folderPagination.total > 0 &&
        folderPagination.page > 1
      ) {
        folderPagination.page = paginationTotalPages(folderPagination);
        await refreshSelectedKnowledgeBaseFolders(accessToken);
        return;
      }
      await refreshFolderOptions(accessToken);
      if (
        selectedFolderId.value &&
        !adminFolders.value.some((folder) => folder.id === selectedFolderId.value)
      ) {
        selectedFolderId.value = "";
      }
      syncFolderEditForm();
    } catch (error) {
      adminFolders.value = [];
      adminFolderOptions.value = [];
      clearPaginationState(folderPagination);
      selectedFolderId.value = "";
      importUploadForm.folderId = "";
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取知识库文件夹失败"),
      };
    } finally {
      importAdminBusy.loadingFolders = false;
    }
  }

  function openCreateFolderModal(): void {
    if (!selectedKnowledgeBase.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请先选择知识库。",
      };
      return;
    }
    folderCreateForm.name = "";
    folderCreateForm.parentId =
      selectedFolderId.value &&
      activeFolders.value.some((folder) => folder.id === selectedFolderId.value)
        ? selectedFolderId.value
        : "";
    importAdminFeedback.value = null;
    folderModalMode.value = "create";
  }

  function openEditFolderModal(folder: AdminFolderData): void {
    selectedFolderId.value = folder.id;
    folderDangerForm.confirmedDelete = false;
    syncFolderEditForm();
    folderModalMode.value = "edit";
  }

  function openDeleteFolderModal(folder: AdminFolderData): void {
    selectedFolderId.value = folder.id;
    folderDangerForm.confirmedDelete = false;
    syncFolderEditForm();
    folderModalMode.value = "delete";
  }

  function closeFolderModal(): void {
    folderModalMode.value = null;
    folderDangerForm.confirmedDelete = false;
  }

  async function submitCreateFolder(): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canCreateFolder.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请选择知识库并填写文件夹名称。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.managingFolder = true;
    try {
      const response = await createAdminFolder(
        knowledgeBase.id,
        {
          name: folderCreateForm.name.trim(),
          parent_id: folderCreateForm.parentId || null,
        },
        accessToken,
      );
      selectedFolderId.value = response.data.id;
      folderPagination.page = 1;
      await refreshSelectedKnowledgeBaseFolders(accessToken);
      importAdminFeedback.value = {
        tone: "success",
        message: "文件夹已创建。",
      };
      closeFolderModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "创建文件夹失败"),
      };
    } finally {
      importAdminBusy.managingFolder = false;
    }
  }

  async function submitPatchFolder(): Promise<void> {
    const folder = selectedFolder.value;
    if (!folder || !canUpdateSelectedFolder.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请选择文件夹并填写文件夹名称。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.managingFolder = true;
    try {
      const response = await patchAdminFolder(
        folder.id,
        {
          name: folderEditForm.name.trim(),
          parent_id: folderEditForm.parentId || null,
          status: folderEditForm.status,
        },
        accessToken,
      );
      selectedFolderId.value = response.data.id;
      await refreshSelectedKnowledgeBaseFolders(accessToken);
      importAdminFeedback.value = {
        tone: "success",
        message: "文件夹已更新。",
      };
      closeFolderModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "更新文件夹失败"),
      };
    } finally {
      importAdminBusy.managingFolder = false;
    }
  }

  async function deleteSelectedFolder(): Promise<void> {
    const folder = selectedFolder.value;
    if (!folder || !folderDangerForm.confirmedDelete) {
      importAdminFeedback.value = {
        tone: "error",
        message: "删除文件夹前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.managingFolder = true;
    try {
      await deleteAdminFolder(folder.id, accessToken, true);
      selectedFolderId.value = "";
      importUploadForm.folderId =
        importUploadForm.folderId === folder.id ? "" : importUploadForm.folderId;
      await refreshSelectedKnowledgeBaseFolders(accessToken);
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
      importAdminFeedback.value = {
        tone: "success",
        message: "文件夹已删除，并已写入访问阻断。",
      };
      closeFolderModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "删除文件夹失败"),
      };
    } finally {
      importAdminBusy.managingFolder = false;
    }
  }

  return {
    closeFolderModal,
    deleteSelectedFolder,
    openCreateFolderModal,
    openDeleteFolderModal,
    openEditFolderModal,
    refreshSelectedKnowledgeBaseFolders,
    submitCreateFolder,
    submitPatchFolder,
  };
}
