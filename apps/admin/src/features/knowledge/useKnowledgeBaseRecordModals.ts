import type { Ref } from "vue";

import type { AdminKnowledgeBaseListItemData } from "@/api/knowledgeBases";
import type {
  DocumentModalMode,
  KnowledgeBaseModalMode,
} from "@/features/knowledge/useKnowledgeModals";

type UseKnowledgeBaseRecordModalsOptions = {
  documentManagerModalOpen: Ref<boolean>;
  documentModalMode: Ref<DocumentModalMode>;
  importAdminFeedback: Ref<{ tone: "success" | "error" | "neutral"; message: string } | null>;
  knowledgeBaseCreateForm: {
    confirmedEnterpriseVisibility: boolean;
  };
  knowledgeBaseDangerForm: {
    confirmedDelete: boolean;
  };
  knowledgeBaseEditForm: {
    confirmedVisibilityExpand: boolean;
  };
  knowledgeBaseIndexForm: {
    confirmedRebuild: boolean;
  };
  knowledgeBaseModalMode: Ref<KnowledgeBaseModalMode>;
  knowledgeBasePermissionForm: {
    confirmedReplace: boolean;
  };
  resetKnowledgeBaseCreateForm: () => void;
  selectKnowledgeBase: (knowledgeBaseId: string) => Promise<void>;
  syncKnowledgeBaseEditForm: () => void;
  syncKnowledgeBasePermissionForm: () => void;
};

export function useKnowledgeBaseRecordModals(options: UseKnowledgeBaseRecordModalsOptions) {
  function openCreateKnowledgeBaseModal(): void {
    options.resetKnowledgeBaseCreateForm();
    options.importAdminFeedback.value = null;
    options.knowledgeBaseModalMode.value = "create";
  }

  async function openEditKnowledgeBaseModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    await options.selectKnowledgeBase(knowledgeBase.id);
    options.knowledgeBaseModalMode.value = "edit";
    options.syncKnowledgeBaseEditForm();
  }

  async function openDeleteKnowledgeBaseModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    options.knowledgeBaseDangerForm.confirmedDelete = false;
    await options.selectKnowledgeBase(knowledgeBase.id);
    options.knowledgeBaseModalMode.value = "delete";
  }

  async function openKnowledgeBasePermissionsModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    await options.selectKnowledgeBase(knowledgeBase.id);
    options.knowledgeBaseModalMode.value = "permissions";
    options.syncKnowledgeBasePermissionForm();
  }

  async function openRebuildKnowledgeBaseIndexModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    options.knowledgeBaseIndexForm.confirmedRebuild = false;
    await options.selectKnowledgeBase(knowledgeBase.id);
    options.knowledgeBaseModalMode.value = "rebuildIndex";
  }

  async function openKnowledgeBaseDocumentManagerModal(
    knowledgeBase: AdminKnowledgeBaseListItemData,
  ): Promise<void> {
    options.importAdminFeedback.value = null;
    await options.selectKnowledgeBase(knowledgeBase.id);
    options.documentManagerModalOpen.value = true;
  }

  function closeKnowledgeBaseDocumentManagerModal(): void {
    options.documentManagerModalOpen.value = false;
    if (options.documentModalMode.value === "details") {
      options.documentModalMode.value = null;
    }
  }

  function closeKnowledgeBaseModal(): void {
    options.knowledgeBaseModalMode.value = null;
    options.knowledgeBaseDangerForm.confirmedDelete = false;
    options.knowledgeBaseCreateForm.confirmedEnterpriseVisibility = false;
    options.knowledgeBaseEditForm.confirmedVisibilityExpand = false;
    options.knowledgeBasePermissionForm.confirmedReplace = false;
    options.knowledgeBaseIndexForm.confirmedRebuild = false;
  }

  return {
    closeKnowledgeBaseDocumentManagerModal,
    closeKnowledgeBaseModal,
    openCreateKnowledgeBaseModal,
    openDeleteKnowledgeBaseModal,
    openEditKnowledgeBaseModal,
    openKnowledgeBaseDocumentManagerModal,
    openKnowledgeBasePermissionsModal,
    openRebuildKnowledgeBaseIndexModal,
  };
}
