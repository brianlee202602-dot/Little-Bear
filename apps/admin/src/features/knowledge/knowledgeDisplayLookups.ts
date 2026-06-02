import type { Ref } from "vue";

import type { AdminCurrentUserCapabilitiesData, CurrentUserDepartment } from "@/api/auth";
import type {
  AdminDepartmentListItemData,
  AdminDepartmentOptionData,
} from "@/api/departments";
import type {
  AdminDocumentData,
  AdminDocumentListItemData,
  ChunkData,
  DocumentVersionData,
} from "@/api/documents";
import type { AdminFolderData, AdminFolderOptionData } from "@/api/folders";
import type { ImportJobData, ImportJobListItemData } from "@/api/imports";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";
import type { PaginationState } from "@/utils/pagination";
import { formatDepartmentLabel } from "@/features/departments/departmentDisplay";
import {
  formatChunkOrdinal as formatChunkOrdinalForDisplay,
  formatDocumentCurrentVersion as formatDocumentCurrentVersionForDisplay,
  formatDocumentVersion,
  formatFolderLabel,
  formatIndexVersionLabel as formatIndexVersionLabelForDisplay,
  formatKnowledgeBaseLabel,
} from "@/features/knowledge/knowledgeDisplay";
import { formatRoleBindingScope as formatRoleBindingScopeForDisplay } from "@/features/users/userDisplay";

interface UseKnowledgeDisplayLookupsDependencies {
  adminDepartmentOptions: Ref<AdminDepartmentOptionData[]>;
  adminDepartments: Ref<AdminDepartmentListItemData[]>;
  adminFolderOptions: Ref<AdminFolderOptionData[]>;
  adminFolders: Ref<AdminFolderData[]>;
  adminKnowledgeBaseOptions: Ref<AdminKnowledgeBaseOptionData[]>;
  adminKnowledgeBases: Ref<AdminKnowledgeBaseListItemData[]>;
  currentUser: Ref<AdminCurrentUserCapabilitiesData | null>;
  documentChunkPagination: PaginationState;
  documentIndexVersionPagination: PaginationState;
  selectedDocumentId: Ref<string>;
  selectedDocumentVersions: Ref<DocumentVersionData[]>;
  selectedKnowledgeBaseDetail: Ref<AdminKnowledgeBaseData | null>;
}

export function useKnowledgeDisplayLookups(options: UseKnowledgeDisplayLookupsDependencies) {
  const {
    adminDepartmentOptions,
    adminDepartments,
    adminFolderOptions,
    adminFolders,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    currentUser,
    documentChunkPagination,
    documentIndexVersionPagination,
    selectedDocumentId,
    selectedDocumentVersions,
    selectedKnowledgeBaseDetail,
  } = options;

  function formatKnowledgeBaseById(knowledgeBaseId: string | null | undefined): string {
    if (!knowledgeBaseId) {
      return "-";
    }
    const knowledgeBase =
      adminKnowledgeBaseOptions.value.find((item) => item.id === knowledgeBaseId) ??
      adminKnowledgeBases.value.find((item) => item.id === knowledgeBaseId);
    return knowledgeBase ? formatKnowledgeBaseLabel(knowledgeBase) : "未读取到知识库";
  }

  function formatFolderById(folderId: string | null): string {
    if (!folderId) {
      return "根目录";
    }
    const folder =
      adminFolderOptions.value.find((item) => item.id === folderId) ??
      adminFolders.value.find((item) => item.id === folderId);
    return folder ? formatFolderLabel(folder) : "未读取到文件夹";
  }

  function departmentSnapshotById(
    departmentId: string,
  ): { code?: string | null; name?: string | null } | null {
    const knowledgeBaseOwner = adminKnowledgeBases.value.find(
      (item) => item.owner_department_id === departmentId,
    );
    const knowledgeBaseDefaultOwner = adminKnowledgeBases.value.find(
      (item) => item.default_document_owner_department_id === departmentId,
    );
    return (
      adminDepartmentOptions.value.find((item) => item.id === departmentId) ??
      adminDepartments.value.find((item) => item.id === departmentId) ??
      currentUser.value?.departments.find(
        (item: CurrentUserDepartment) => item.id === departmentId,
      ) ??
      (selectedKnowledgeBaseDetail.value?.owner_department?.id === departmentId
        ? selectedKnowledgeBaseDetail.value.owner_department
        : null) ??
      (selectedKnowledgeBaseDetail.value?.default_document_owner_department?.id === departmentId
        ? selectedKnowledgeBaseDetail.value.default_document_owner_department
        : null) ??
      (knowledgeBaseOwner?.owner_department_name
        ? { name: knowledgeBaseOwner.owner_department_name }
        : null) ??
      (knowledgeBaseDefaultOwner?.default_document_owner_department_name
        ? { name: knowledgeBaseDefaultOwner.default_document_owner_department_name }
        : null) ??
      null
    );
  }

  function formatDepartmentById(departmentId: string | null | undefined): string {
    if (!departmentId) {
      return "-";
    }
    const department = departmentSnapshotById(departmentId);
    return department ? formatDepartmentLabel(department) : "未读取到部门";
  }

  function formatDocumentVersionById(versionId: string | null | undefined): string {
    if (!versionId) {
      return "-";
    }
    const version = selectedDocumentVersions.value.find((item) => item.id === versionId);
    return version ? formatDocumentVersion(version) : "-";
  }

  function formatDocumentCurrentVersion(
    document: AdminDocumentData | AdminDocumentListItemData,
  ): string {
    return formatDocumentCurrentVersionForDisplay(document, {
      formatDocumentVersionById,
      selectedDocumentId: selectedDocumentId.value,
    });
  }

  function formatIndexVersionLabel(index: number): string {
    return formatIndexVersionLabelForDisplay(index, documentIndexVersionPagination);
  }

  function formatChunkOrdinal(chunk: ChunkData, index: number): string {
    return formatChunkOrdinalForDisplay(chunk, index, documentChunkPagination);
  }

  function formatImportJobKnowledgeBase(job: ImportJobData | ImportJobListItemData): string {
    const knowledgeBase =
      adminKnowledgeBaseOptions.value.find((item) => item.id === job.kb_id) ??
      adminKnowledgeBases.value.find((item) => item.id === job.kb_id);
    return knowledgeBase ? formatKnowledgeBaseLabel(knowledgeBase) : "未读取到知识库";
  }

  function formatRoleBindingScope(
    binding: Parameters<typeof formatRoleBindingScopeForDisplay>[0],
  ): string {
    return formatRoleBindingScopeForDisplay(binding, {
      formatDepartmentById,
      formatKnowledgeBaseById,
    });
  }

  return {
    formatChunkOrdinal,
    formatDepartmentById,
    formatDocumentCurrentVersion,
    formatFolderById,
    formatImportJobKnowledgeBase,
    formatIndexVersionLabel,
    formatKnowledgeBaseById,
    formatRoleBindingScope,
  };
}
