import type { AdminKnowledgeBaseData } from "@/api/knowledgeBases";
import {
  knowledgeBaseListItemFromDetail,
  knowledgeBaseOptionFromDetail,
} from "@/features/knowledge/knowledgeBaseRecordHelpers";
import type { UseKnowledgeBaseRecordsDependencies } from "@/features/knowledge/useKnowledgeBaseRecords";

type UseKnowledgeBaseCrudActionDependencies = UseKnowledgeBaseRecordsDependencies & {
  closeKnowledgeBaseModal: () => void;
};

export function useKnowledgeBaseCrudActions(options: UseKnowledgeBaseCrudActionDependencies) {
  const {
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    buildDepartmentKnowledgeBaseAccessRules,
    canCreateKnowledgeBase,
    canManageKnowledgeBases,
    canReplaceSelectedKnowledgeBasePermissions,
    canUpdateSelectedKnowledgeBase,
    clearBatchDocumentSelection,
    clearPaginationState,
    clearSelectedDocumentDetails,
    clearSelectedDocumentMetadata,
    closeKnowledgeBaseModal,
    createAdminKnowledgeBase,
    deleteAdminKnowledgeBase,
    documentPagination,
    ensureAccessToken,
    folderDangerForm,
    folderPagination,
    getAdminKnowledgeBase,
    importAdminBusy,
    importAdminFeedback,
    importSearchForm,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBasePermissionForm,
    normalizeErrorMessage,
    patchAdminKnowledgeBase,
    putKnowledgeBasePermissions,
    refreshKnowledgeBaseAdminState,
    refreshSelectedKnowledgeBaseDocuments,
    refreshSelectedKnowledgeBaseFolders,
    selectedDocumentId,
    selectedFolderId,
    selectedKnowledgeBase,
    selectedKnowledgeBaseDetail,
    selectedKnowledgeBaseId,
    syncFolderEditForm,
    syncKnowledgeBaseEditForm,
    syncKnowledgeBasePermissionForm,
  } = options;

  async function refreshSelectedKnowledgeBaseDetail(existingAccessToken?: string): Promise<void> {
    if (!selectedKnowledgeBaseId.value || !canManageKnowledgeBases.value) {
      selectedKnowledgeBaseDetail.value = null;
      syncKnowledgeBaseEditForm();
      syncKnowledgeBasePermissionForm();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }
    const response = await getAdminKnowledgeBase(selectedKnowledgeBaseId.value, accessToken);
    selectedKnowledgeBaseDetail.value = response.data;
    upsertKnowledgeBase(response.data);
    syncKnowledgeBaseEditForm();
    syncKnowledgeBasePermissionForm();
  }

  async function submitCreateKnowledgeBase(): Promise<void> {
    if (!canCreateKnowledgeBase.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请填写知识库名称和所属部门。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.creating = true;
    try {
      const response = await createAdminKnowledgeBase(
        {
          name: knowledgeBaseCreateForm.name.trim(),
          owner_department_id: knowledgeBaseCreateForm.ownerDepartmentId.trim(),
          kb_visibility: knowledgeBaseCreateForm.kbVisibility,
          default_document_visibility: knowledgeBaseCreateForm.defaultDocumentVisibility,
          default_document_owner_department_id:
            knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim(),
          access_rules: buildDepartmentKnowledgeBaseAccessRules(
            knowledgeBaseCreateForm.kbVisibility === "enterprise"
              ? []
              : [
                  ...knowledgeBaseCreateForm.accessDepartmentIds,
                  knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim(),
                ],
          ),
          config_scope_id: knowledgeBaseCreateForm.configScopeId.trim() || null,
        },
        accessToken,
        knowledgeBaseCreateForm.confirmedEnterpriseVisibility,
      );
      upsertKnowledgeBase(response.data);
      selectedKnowledgeBaseId.value = response.data.id;
      importSearchForm.kbId = response.data.id;
      await refreshKnowledgeBaseAdminState();
      importAdminFeedback.value = {
        tone: "success",
        message: "知识库已创建。",
      };
      closeKnowledgeBaseModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "创建知识库失败"),
      };
    } finally {
      importAdminBusy.creating = false;
    }
  }

  async function selectKnowledgeBase(kbId: string): Promise<void> {
    selectedKnowledgeBaseId.value = kbId;
    selectedKnowledgeBaseDetail.value = null;
    selectedFolderId.value = "";
    selectedDocumentId.value = "";
    clearPaginationState(folderPagination);
    clearPaginationState(documentPagination);
    clearSelectedDocumentDetails();
    clearSelectedDocumentMetadata();
    clearBatchDocumentSelection();
    knowledgeBaseDangerForm.confirmedDelete = false;
    folderDangerForm.confirmedDelete = false;
    syncKnowledgeBaseEditForm();
    syncKnowledgeBasePermissionForm();
    syncFolderEditForm();

    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }
    try {
      if (canManageKnowledgeBases.value) {
        await refreshSelectedKnowledgeBaseDetail(accessToken);
      }
      await refreshSelectedKnowledgeBaseFolders(accessToken);
      await refreshSelectedKnowledgeBaseDocuments(accessToken);
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取知识库详情、文件夹或文档失败"),
      };
    }
  }

  async function submitPatchKnowledgeBase(): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canUpdateSelectedKnowledgeBase.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请选择知识库并填写知识库名称。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.updating = true;
    try {
      const response = await patchAdminKnowledgeBase(
        knowledgeBase.id,
        {
          name: knowledgeBaseEditForm.name.trim(),
          status: knowledgeBaseEditForm.status,
          kb_visibility: knowledgeBaseEditForm.kbVisibility,
          default_document_visibility: knowledgeBaseEditForm.defaultDocumentVisibility,
          default_document_owner_department_id:
            knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId.trim(),
          config_scope_id: knowledgeBaseEditForm.configScopeId.trim() || null,
        },
        accessToken,
        knowledgeBaseEditForm.confirmedVisibilityExpand,
      );
      upsertKnowledgeBase(response.data);
      selectedKnowledgeBaseId.value = response.data.id;
      await refreshKnowledgeBaseAdminState();
      importAdminFeedback.value = {
        tone: "success",
        message: "知识库已更新。",
      };
      closeKnowledgeBaseModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "更新知识库失败"),
      };
    } finally {
      importAdminBusy.updating = false;
    }
  }

  async function submitKnowledgeBasePermissions(): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canReplaceSelectedKnowledgeBasePermissions.value) {
      importAdminFeedback.value = {
        tone: "error",
        message: "请选择知识库、填写默认文档所属部门并勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.updatingPermissions = true;
    try {
      await putKnowledgeBasePermissions(
        knowledgeBase.id,
        {
          kb_visibility: knowledgeBasePermissionForm.kbVisibility,
          default_document_visibility: knowledgeBasePermissionForm.defaultDocumentVisibility,
          default_document_owner_department_id:
            knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim(),
          access_rules: buildDepartmentKnowledgeBaseAccessRules(
            knowledgeBasePermissionForm.kbVisibility === "enterprise"
              ? []
              : [
                  ...knowledgeBasePermissionForm.accessDepartmentIds,
                  knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim(),
                ],
          ),
        },
        accessToken,
        true,
      );
      await refreshKnowledgeBaseAdminState();
      importAdminFeedback.value = {
        tone: "success",
        message: "知识库权限策略已更新。",
      };
      closeKnowledgeBaseModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "更新知识库权限失败"),
      };
    } finally {
      importAdminBusy.updatingPermissions = false;
    }
  }

  async function deleteSelectedKnowledgeBase(): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !knowledgeBaseDangerForm.confirmedDelete) {
      importAdminFeedback.value = {
        tone: "error",
        message: "删除知识库前必须勾选确认项。",
      };
      return;
    }
    const accessToken = await ensureAccessToken();
    if (!accessToken) {
      return;
    }

    importAdminBusy.deleting = true;
    try {
      await deleteAdminKnowledgeBase(knowledgeBase.id, accessToken, true);
      selectedKnowledgeBaseId.value = "";
      knowledgeBaseDangerForm.confirmedDelete = false;
      await refreshKnowledgeBaseAdminState();
      importAdminFeedback.value = {
        tone: "success",
        message: "知识库已删除，并已创建索引清理任务。",
      };
      closeKnowledgeBaseModal();
    } catch (error) {
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "删除知识库失败"),
      };
    } finally {
      importAdminBusy.deleting = false;
    }
  }

  function upsertKnowledgeBase(knowledgeBase: AdminKnowledgeBaseData): void {
    const index = adminKnowledgeBases.value.findIndex(
      (item: { id: string }) => item.id === knowledgeBase.id,
    );
    const listItem = knowledgeBaseListItemFromDetail(knowledgeBase);
    if (index >= 0) {
      adminKnowledgeBases.value[index] = listItem;
    } else {
      adminKnowledgeBases.value = [listItem, ...adminKnowledgeBases.value];
    }
    const option = knowledgeBaseOptionFromDetail(knowledgeBase);
    const optionIndex = adminKnowledgeBaseOptions.value.findIndex(
      (item: { id: string }) => item.id === knowledgeBase.id,
    );
    if (option.status === "active") {
      if (optionIndex >= 0) {
        adminKnowledgeBaseOptions.value[optionIndex] = option;
      } else {
        adminKnowledgeBaseOptions.value = [option, ...adminKnowledgeBaseOptions.value];
      }
    } else if (optionIndex >= 0) {
      adminKnowledgeBaseOptions.value = adminKnowledgeBaseOptions.value.filter(
        (item: { id: string }) => item.id !== knowledgeBase.id,
      );
    }
  }

  return {
    deleteSelectedKnowledgeBase,
    refreshSelectedKnowledgeBaseDetail,
    selectKnowledgeBase,
    submitCreateKnowledgeBase,
    submitKnowledgeBasePermissions,
    submitPatchKnowledgeBase,
    upsertKnowledgeBase,
  };
}
