import type { ComputedRef, Ref } from "vue";

import type { AdminFolderData } from "@/api/folders";
import type { AdminFolderOptionData } from "@/api/folders";
import type { AdminKnowledgeBaseOptionData } from "@/api/knowledgeBases";
import type { AdminKnowledgeBaseData, AdminKnowledgeBaseListItemData } from "@/api/knowledgeBases";
import type { AdminFolderOptionListResponse } from "@/api/folders";
import type { AdminKnowledgeBaseOptionListResponse } from "@/api/knowledgeBases";

export interface UseKnowledgeOptionsDependencies {
  adminFolderOptions: Ref<AdminFolderOptionData[]>;
  adminFolders: Ref<AdminFolderData[]>;
  adminKnowledgeBaseOptions: Ref<AdminKnowledgeBaseOptionData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  canManageFolders: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  ensureAccessToken: () => Promise<string | null>;
  importUploadForm: {
    folderId: string;
  };
  listAdminFolderOptions: (
    knowledgeBaseId: string,
    accessToken: string,
    params: { keyword?: string; page_size: number; status?: string },
  ) => Promise<AdminFolderOptionListResponse>;
  listAdminKnowledgeBaseOptions: (
    accessToken: string,
    params: { keyword?: string; page_size: number; status?: string },
  ) => Promise<AdminKnowledgeBaseOptionListResponse>;
  optionSearchForm: {
    folderKeyword: string;
    knowledgeBaseKeyword: string;
  };
  selectedKnowledgeBase: ComputedRef<AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
  selectorPageSize: number;
  syncRoleBindingScopeDefault: () => void;
  uniqueById: <T extends { id: string }>(items: T[]) => T[];
}

export function useKnowledgeOptions(options: UseKnowledgeOptionsDependencies) {
  const {
    adminFolderOptions,
    adminFolders,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    canManageFolders,
    canManageKnowledgeBases,
    ensureAccessToken,
    importUploadForm,
    listAdminFolderOptions,
    listAdminKnowledgeBaseOptions,
    optionSearchForm,
    selectedKnowledgeBase,
    selectedKnowledgeBaseDetail,
    selectorPageSize,
    syncRoleBindingScopeDefault,
    uniqueById,
  } = options;

  async function refreshKnowledgeBaseOptions(existingAccessToken?: string): Promise<void> {
    if (!canManageKnowledgeBases.value) {
      adminKnowledgeBaseOptions.value = [];
      syncRoleBindingScopeDefault();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminKnowledgeBaseOptions(accessToken, {
      keyword: optionSearchForm.knowledgeBaseKeyword.trim() || undefined,
      status: "active",
      page_size: selectorPageSize,
    });
    adminKnowledgeBaseOptions.value = mergeKnowledgeBaseOptions(response.data);
    syncRoleBindingScopeDefault();
  }

  async function refreshFolderOptions(existingAccessToken?: string): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canManageFolders.value) {
      adminFolderOptions.value = [];
      importUploadForm.folderId = "";
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await listAdminFolderOptions(knowledgeBase.id, accessToken, {
      keyword: optionSearchForm.folderKeyword.trim() || undefined,
      status: "active",
      page_size: selectorPageSize,
    });
    adminFolderOptions.value = mergeFolderOptions(response.data);
  }

  function refreshKnowledgeBaseOptionsFromSearch(): void {
    void refreshKnowledgeBaseOptions();
  }

  function refreshFolderOptionsFromSearch(): void {
    void refreshFolderOptions();
  }

  function mergeKnowledgeBaseOptions(
    incomingOptions: AdminKnowledgeBaseOptionData[],
  ): AdminKnowledgeBaseOptionData[] {
    const pinned = [
      ...adminKnowledgeBases.value.map((knowledgeBase) => ({
        id: knowledgeBase.id,
        name: knowledgeBase.name,
        status: knowledgeBase.status,
      })),
      ...(selectedKnowledgeBaseDetail.value
        ? [
            {
              id: selectedKnowledgeBaseDetail.value.id,
              name: selectedKnowledgeBaseDetail.value.name,
              status: selectedKnowledgeBaseDetail.value.status,
            },
          ]
        : []),
    ];
    return uniqueById([...incomingOptions, ...pinned]);
  }

  function mergeFolderOptions(incomingOptions: AdminFolderOptionData[]): AdminFolderOptionData[] {
    const pinned = adminFolders.value.map((folder) => ({
      id: folder.id,
      name: folder.name,
      status: folder.status,
    }));
    return uniqueById([...incomingOptions, ...pinned]);
  }

  return {
    refreshFolderOptions,
    refreshFolderOptionsFromSearch,
    refreshKnowledgeBaseOptions,
    refreshKnowledgeBaseOptionsFromSearch,
  };
}
