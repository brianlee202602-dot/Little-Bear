import { computed } from "vue";

import {
  buildDepartmentKnowledgeBaseAccessRules,
  departmentCanQueryKnowledgeBase,
  queryDepartmentIdsForKnowledgeBase,
} from "@/features/knowledge/knowledgePermissionRules";
import type { KnowledgePermissionOptions } from "@/features/knowledge/knowledgePermissionTypes";

export function useKnowledgePermissions(options: KnowledgePermissionOptions) {
  const selectedDocumentParentKnowledgeBase = computed(() => {
    const document = options.selectedAdminDocument.value;
    if (!document) {
      return options.selectedKnowledgeBaseDetail.value?.id === options.selectedKnowledgeBaseId.value
        ? options.selectedKnowledgeBaseDetail.value
        : null;
    }
    return options.selectedKnowledgeBaseDetail.value?.id === document.kb_id
      ? options.selectedKnowledgeBaseDetail.value
      : null;
  });
  const documentPermissionParentConflict = computed(() => {
    const knowledgeBase = selectedDocumentParentKnowledgeBase.value;
    if (!knowledgeBase || options.documentPermissionForm.visibility === "enterprise") {
      return "";
    }
    const ownerDepartmentId = options.documentPermissionForm.ownerDepartmentId.trim();
    if (ownerDepartmentId && !departmentCanQueryKnowledgeBase(knowledgeBase, ownerDepartmentId)) {
      return `${options.formatDepartmentById(ownerDepartmentId)} 不能查询父知识库；请先在知识库权限中授予该部门查询权限。`;
    }
    return "";
  });
  const importUploadPermissionParentConflict = computed(() => {
    const knowledgeBase =
      options.selectedKnowledgeBaseDetail.value?.id === options.importUploadForm.kbId
        ? options.selectedKnowledgeBaseDetail.value
        : null;
    if (!knowledgeBase || options.importUploadForm.visibility === "enterprise") {
      return "";
    }
    const ownerDepartmentId =
      knowledgeBase.default_document_owner_department_id ?? knowledgeBase.owner_department_id ?? "";
    if (ownerDepartmentId && !departmentCanQueryKnowledgeBase(knowledgeBase, ownerDepartmentId)) {
      return `${options.formatDepartmentById(ownerDepartmentId)} 不能查询目标知识库；请先在知识库权限中授予该部门查询权限。`;
    }
    return "";
  });
  const canUploadImportFiles = computed(
    () =>
      options.canImportDocuments.value &&
      options.selectedImportFiles.value.length > 0 &&
      options.importUploadForm.kbId.trim().length > 0 &&
      !importUploadPermissionParentConflict.value &&
      !options.importAdminBusy.uploading,
  );
  const canCreateKnowledgeBase = computed(
    () =>
      options.canManageKnowledgeBases.value &&
      options.knowledgeBaseCreateForm.name.trim().length > 0 &&
      options.knowledgeBaseCreateForm.ownerDepartmentId.trim().length > 0 &&
      options.knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
      (options.knowledgeBaseCreateForm.kbVisibility === "enterprise" ||
        options.knowledgeBaseCreateForm.accessDepartmentIds.length > 0) &&
      (options.knowledgeBaseCreateForm.kbVisibility !== "enterprise" ||
        options.knowledgeBaseCreateForm.confirmedEnterpriseVisibility) &&
      !options.importAdminBusy.creating,
  );
  const canUpdateSelectedKnowledgeBase = computed(
    () =>
      options.canManageKnowledgeBases.value &&
      Boolean(options.selectedKnowledgeBase.value) &&
      options.knowledgeBaseEditForm.name.trim().length > 0 &&
      options.knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
      !(
        options.selectedKnowledgeBase.value?.kb_visibility !== "enterprise" &&
        options.knowledgeBaseEditForm.kbVisibility === "enterprise" &&
        !options.knowledgeBaseEditForm.confirmedVisibilityExpand
      ) &&
      !options.importAdminBusy.updating,
  );
  const canDeleteSelectedKnowledgeBase = computed(
    () =>
      options.canManageKnowledgeBases.value &&
      Boolean(options.selectedKnowledgeBase.value) &&
      options.knowledgeBaseDangerForm.confirmedDelete &&
      !options.importAdminBusy.deleting,
  );
  const canRebuildSelectedKnowledgeBaseIndex = computed(
    () =>
      options.canIndexDocuments.value &&
      options.selectedKnowledgeBase.value?.status === "active" &&
      options.knowledgeBaseIndexForm.confirmedRebuild &&
      !options.importAdminBusy.rebuildingIndex,
  );
  const canCreateFolder = computed(
    () =>
      options.canManageFolders.value &&
      Boolean(options.selectedKnowledgeBase.value) &&
      options.folderCreateForm.name.trim().length > 0 &&
      !options.importAdminBusy.managingFolder,
  );
  const canUpdateSelectedFolder = computed(
    () =>
      options.canManageFolders.value &&
      Boolean(options.selectedFolder.value) &&
      options.folderEditForm.name.trim().length > 0 &&
      !options.importAdminBusy.managingFolder,
  );
  const canDeleteSelectedFolder = computed(
    () =>
      options.canManageFolders.value &&
      Boolean(options.selectedFolder.value) &&
      options.folderDangerForm.confirmedDelete &&
      !options.importAdminBusy.managingFolder,
  );
  const canReplaceSelectedKnowledgeBasePermissions = computed(
    () =>
      options.canManagePermissions.value &&
      Boolean(options.selectedKnowledgeBase.value) &&
      options.knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId.trim().length > 0 &&
      (options.knowledgeBasePermissionForm.kbVisibility === "enterprise" ||
        options.knowledgeBasePermissionForm.accessDepartmentIds.length > 0) &&
      options.knowledgeBasePermissionForm.confirmedReplace &&
      !options.importAdminBusy.updatingPermissions,
  );
  const canReplaceSelectedDocumentPermissions = computed(
    () =>
      options.canManagePermissions.value &&
      Boolean(options.selectedAdminDocument.value) &&
      options.documentPermissionForm.ownerDepartmentId.trim().length > 0 &&
      !documentPermissionParentConflict.value &&
      options.documentPermissionForm.confirmedReplace &&
      !options.importAdminBusy.updatingPermissions,
  );

  function syncKnowledgeBaseCreateOwnerDefault(): void {
    if (
      options.knowledgeBaseCreateForm.ownerDepartmentId &&
      options.activeDepartments.value.some(
        (department) => department.id === options.knowledgeBaseCreateForm.ownerDepartmentId,
      )
    ) {
      return;
    }
    const defaultDepartment =
      options.activeDepartments.value.find((department) => department.is_default) ??
      options.currentUser.value?.departments.find((department) => department.status === "active") ??
      options.activeDepartments.value[0];
    options.knowledgeBaseCreateForm.ownerDepartmentId =
      defaultDepartment?.id ?? options.knowledgeBaseCreateForm.ownerDepartmentId;
    options.knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId =
      options.knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId ||
      options.knowledgeBaseCreateForm.ownerDepartmentId;
  }

  function syncKnowledgeBaseEditForm(): void {
    const knowledgeBase =
      options.selectedKnowledgeBaseDetail.value?.id === options.selectedKnowledgeBaseId.value
        ? options.selectedKnowledgeBaseDetail.value
        : null;
    options.knowledgeBaseEditForm.name = knowledgeBase?.name ?? "";
    options.knowledgeBaseEditForm.status = knowledgeBase?.status ?? "active";
    options.knowledgeBaseEditForm.kbVisibility = knowledgeBase?.kb_visibility ?? "enterprise";
    options.knowledgeBaseEditForm.defaultDocumentVisibility =
      knowledgeBase?.default_document_visibility ?? "department";
    options.knowledgeBaseEditForm.defaultDocumentOwnerDepartmentId =
      knowledgeBase?.default_document_owner_department_id ?? "";
    options.knowledgeBaseEditForm.configScopeId = knowledgeBase?.config_scope_id ?? "";
    options.knowledgeBaseEditForm.confirmedVisibilityExpand = false;
  }

  function syncKnowledgeBasePermissionForm(): void {
    const knowledgeBase =
      options.selectedKnowledgeBaseDetail.value?.id === options.selectedKnowledgeBaseId.value
        ? options.selectedKnowledgeBaseDetail.value
        : null;
    options.knowledgeBasePermissionForm.kbVisibility = knowledgeBase?.kb_visibility ?? "enterprise";
    options.knowledgeBasePermissionForm.defaultDocumentVisibility =
      knowledgeBase?.default_document_visibility ?? "department";
    options.knowledgeBasePermissionForm.defaultDocumentOwnerDepartmentId =
      knowledgeBase?.default_document_owner_department_id ??
      knowledgeBase?.owner_department_id ??
      "";
    options.knowledgeBasePermissionForm.accessDepartmentIds = knowledgeBase
      ? queryDepartmentIdsForKnowledgeBase(knowledgeBase)
      : [];
    options.knowledgeBasePermissionForm.confirmedReplace = false;
  }

  function syncFolderEditForm(): void {
    const folder = options.selectedFolder.value;
    options.folderEditForm.name = folder?.name ?? "";
    options.folderEditForm.parentId = folder?.parent_id ?? "";
    options.folderEditForm.status = folder?.status ?? "active";
  }

  function syncDocumentPermissionForm(): void {
    const document = options.selectedAdminDocument.value;
    options.documentPermissionForm.visibility = document?.visibility ?? "department";
    options.documentPermissionForm.ownerDepartmentId = document?.owner_department_id ?? "";
    options.documentPermissionForm.confirmedReplace = false;
  }

  function resetKnowledgeBaseCreateForm(): void {
    options.knowledgeBaseCreateForm.name = "";
    options.knowledgeBaseCreateForm.kbVisibility = "enterprise";
    options.knowledgeBaseCreateForm.defaultDocumentVisibility = "department";
    options.knowledgeBaseCreateForm.defaultDocumentOwnerDepartmentId = "";
    options.knowledgeBaseCreateForm.accessDepartmentIds = [];
    options.knowledgeBaseCreateForm.configScopeId = "";
    options.knowledgeBaseCreateForm.confirmedEnterpriseVisibility = false;
    syncKnowledgeBaseCreateOwnerDefault();
  }

  return {
    buildDepartmentKnowledgeBaseAccessRules,
    canCreateFolder,
    canCreateKnowledgeBase,
    canDeleteSelectedFolder,
    canDeleteSelectedKnowledgeBase,
    canRebuildSelectedKnowledgeBaseIndex,
    canReplaceSelectedDocumentPermissions,
    canReplaceSelectedKnowledgeBasePermissions,
    canUpdateSelectedFolder,
    canUpdateSelectedKnowledgeBase,
    canUploadImportFiles,
    departmentCanQueryKnowledgeBase,
    documentPermissionParentConflict,
    importUploadPermissionParentConflict,
    queryDepartmentIdsForKnowledgeBase,
    resetKnowledgeBaseCreateForm,
    selectedDocumentParentKnowledgeBase,
    syncDocumentPermissionForm,
    syncFolderEditForm,
    syncKnowledgeBaseCreateOwnerDefault,
    syncKnowledgeBaseEditForm,
    syncKnowledgeBasePermissionForm,
  };
}
