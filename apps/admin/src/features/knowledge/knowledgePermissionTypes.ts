import type { ComputedRef, Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData } from "@/api/auth";
import type { AdminDepartmentListItemData, AdminDepartmentOptionData } from "@/api/departments";
import type { AdminDocumentData } from "@/api/documents";
import type { AdminFolderData } from "@/api/folders";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
} from "@/api/knowledgeBases";

export type ImportBusyState = {
  creating: boolean;
  updating: boolean;
  deleting: boolean;
  managingFolder: boolean;
  uploading: boolean;
  updatingPermissions: boolean;
  rebuildingIndex: boolean;
};

export type KnowledgeBaseCreateForm = {
  name: string;
  ownerDepartmentId: string;
  kbVisibility: "enterprise" | "department_acl" | "private";
  defaultDocumentVisibility: "department" | "enterprise";
  defaultDocumentOwnerDepartmentId: string;
  accessDepartmentIds: string[];
  configScopeId: string;
  confirmedEnterpriseVisibility: boolean;
};

export type KnowledgeBaseEditForm = {
  name: string;
  status: "active" | "disabled" | "archived";
  kbVisibility: "enterprise" | "department_acl" | "private";
  defaultDocumentVisibility: "department" | "enterprise";
  defaultDocumentOwnerDepartmentId: string;
  configScopeId: string;
  confirmedVisibilityExpand: boolean;
};

export type KnowledgeBasePermissionForm = {
  kbVisibility: "enterprise" | "department_acl" | "private";
  defaultDocumentVisibility: "department" | "enterprise";
  defaultDocumentOwnerDepartmentId: string;
  accessDepartmentIds: string[];
  confirmedReplace: boolean;
};

export type DocumentPermissionForm = {
  visibility: "department" | "enterprise";
  ownerDepartmentId: string;
  confirmedReplace: boolean;
};

export type FolderEditForm = {
  name: string;
  parentId: string;
  status: "active" | "disabled" | "archived";
};

export type KnowledgePermissionOptions = {
  activeDepartments: ComputedRef<AdminDepartmentOptionData[]>;
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  canImportDocuments: ComputedRef<boolean>;
  canIndexDocuments: ComputedRef<boolean>;
  canManageFolders: ComputedRef<boolean>;
  canManageKnowledgeBases: ComputedRef<boolean>;
  canManagePermissions: ComputedRef<boolean>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  documentPermissionForm: DocumentPermissionForm;
  folderCreateForm: { name: string };
  folderDangerForm: { confirmedDelete: boolean };
  formatDepartmentById: (departmentId: string | null | undefined) => string;
  folderEditForm: FolderEditForm;
  importAdminBusy: ImportBusyState;
  importUploadForm: { kbId: string; visibility: "department" | "enterprise" };
  knowledgeBaseCreateForm: KnowledgeBaseCreateForm;
  knowledgeBaseDangerForm: { confirmedDelete: boolean };
  knowledgeBaseEditForm: KnowledgeBaseEditForm;
  knowledgeBaseIndexForm: { confirmedRebuild: boolean };
  knowledgeBasePermissionForm: KnowledgeBasePermissionForm;
  selectedAdminDocument: ComputedRef<AdminDocumentData | null>;
  selectedFolder: ComputedRef<AdminFolderData | null>;
  selectedKnowledgeBase: ComputedRef<AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
  selectedKnowledgeBaseId: Ref<string>;
  selectedImportKnowledgeBase: ComputedRef<
    AdminKnowledgeBaseData | AdminKnowledgeBaseListItemData | null
  >;
  selectedImportFiles: Ref<File[]>;
};
