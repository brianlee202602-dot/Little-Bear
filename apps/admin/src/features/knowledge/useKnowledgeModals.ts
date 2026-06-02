import { reactive, ref } from "vue";

export type KnowledgeBaseModalMode =
  | "create"
  | "edit"
  | "delete"
  | "upload"
  | "permissions"
  | "rebuildIndex"
  | null;
export type FolderModalMode = "create" | "edit" | "delete" | null;
export type DocumentModalMode = "permissions" | "details" | null;

export function useKnowledgeModals() {
  const selectedKnowledgeBaseId = ref("");
  const selectedFolderId = ref("");
  const selectedDocumentId = ref("");
  const knowledgeBaseModalMode = ref<KnowledgeBaseModalMode>(null);
  const documentManagerModalOpen = ref(false);
  const folderModalMode = ref<FolderModalMode>(null);
  const documentModalMode = ref<DocumentModalMode>(null);
  const selectedImportFiles = ref<File[]>([]);
  const importFileInputKey = ref(0);

  const importUploadForm = reactive({
    kbId: "",
    folderId: "",
    visibility: "department" as "department" | "enterprise",
    idempotencyKey: "",
  });
  const knowledgeBaseCreateForm = reactive({
    name: "",
    ownerDepartmentId: "",
    kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
    defaultDocumentVisibility: "department" as "department" | "enterprise",
    defaultDocumentOwnerDepartmentId: "",
    accessDepartmentIds: [] as string[],
    configScopeId: "",
    confirmedEnterpriseVisibility: false,
  });
  const knowledgeBaseEditForm = reactive({
    name: "",
    status: "active" as "active" | "disabled" | "archived",
    kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
    defaultDocumentVisibility: "department" as "department" | "enterprise",
    defaultDocumentOwnerDepartmentId: "",
    configScopeId: "",
    confirmedVisibilityExpand: false,
  });
  const knowledgeBasePermissionForm = reactive({
    kbVisibility: "enterprise" as "enterprise" | "department_acl" | "private",
    defaultDocumentVisibility: "department" as "department" | "enterprise",
    defaultDocumentOwnerDepartmentId: "",
    accessDepartmentIds: [] as string[],
    confirmedReplace: false,
  });
  const knowledgeBaseIndexForm = reactive({
    confirmedRebuild: false,
  });
  const knowledgeBaseDangerForm = reactive({
    confirmedDelete: false,
  });
  const folderCreateForm = reactive({
    name: "",
    parentId: "",
  });
  const folderEditForm = reactive({
    name: "",
    parentId: "",
    status: "active" as "active" | "disabled" | "archived",
  });
  const folderDangerForm = reactive({
    confirmedDelete: false,
  });
  const documentPermissionForm = reactive({
    visibility: "department" as "department" | "enterprise",
    ownerDepartmentId: "",
    confirmedReplace: false,
  });
  const documentIndexForm = reactive({
    confirmedRebuild: false,
    confirmedBatchRebuild: false,
    confirmedCleanup: false,
  });
  const indexRetryForm = reactive({
    confirmedRetry: false,
  });

  return {
    documentIndexForm,
    documentManagerModalOpen,
    documentModalMode,
    documentPermissionForm,
    folderCreateForm,
    folderDangerForm,
    folderEditForm,
    folderModalMode,
    importFileInputKey,
    importUploadForm,
    indexRetryForm,
    knowledgeBaseCreateForm,
    knowledgeBaseDangerForm,
    knowledgeBaseEditForm,
    knowledgeBaseIndexForm,
    knowledgeBaseModalMode,
    knowledgeBasePermissionForm,
    selectedDocumentId,
    selectedFolderId,
    selectedImportFiles,
    selectedKnowledgeBaseId,
  };
}
