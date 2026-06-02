<script setup lang="ts">
import { computed, onMounted, reactive } from "vue";

import "@/features/knowledge/knowledgeDocuments.css";
import { useAdminCapabilityProvider } from "@/app/providers/adminCapabilityProvider";
import { useAdminSessionProvider } from "@/app/providers/adminSessionProvider";
import { formatDepartmentLabel, formatDepartmentList } from "@/features/departments/departmentDisplay";
import { useDepartmentLookupRuntime } from "@/features/departments/runtime/useDepartmentLookupRuntime";
import KnowledgeBaseAdminContainer from "@/features/knowledge/KnowledgeBaseAdminContainer.vue";
import { createKnowledgeAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import { useKnowledgeDisplayLookups } from "@/features/knowledge/knowledgeDisplayLookups";
import {
  documentIndexStatusTone,
  documentLifecycleStatusTone,
  documentVersionStatusTone,
  documentVisibilityLabel,
  folderStatusTone,
  formatChunkPageRange,
  formatDocumentCount,
  formatDocumentVersion,
  formatFileSize,
  formatFolderLabel,
  formatImportJobTitle,
  formatKnowledgeBaseLabel,
  importJobStageLabel,
  importJobStatusTone,
  indexVersionStatusTone,
  knowledgeBaseStatusTone,
  knowledgeBaseVisibilityLabel,
} from "@/features/knowledge/knowledgeDisplay";
import { useKnowledgeAdminRuntime } from "@/features/knowledge/useKnowledgeAdminRuntime";
import {
  changePaginationPage,
  changePaginationPageSize,
  paginationEnd,
  paginationStart,
  refreshFirstPage,
} from "@/utils/pagination";
import { formatAuditTime } from "@/utils/date";
import {
  formatStatusOption,
  formatStatusText,
  toneClass,
} from "@/utils/display";
import { normalizeErrorMessage } from "@/utils/errors";

const pageSizeOptions = [10, 20, 50, 100, 200];
const selectorPageSize = 20;
const optionSearchForm = reactive({
  departmentKeyword: "",
  knowledgeBaseKeyword: "",
  folderKeyword: "",
});

const capabilities = useAdminCapabilityProvider();
const session = useAdminSessionProvider();
let syncKnowledgeBaseCreateOwnerDefaultFromRuntime = (): void => undefined;

const {
  adminDepartmentOptions,
  adminDepartments,
  refreshDepartmentOptions,
  refreshDepartmentOptionsFromSearch,
} = useDepartmentLookupRuntime({
  canReadDepartments: capabilities.canReadDepartments,
  ensureAccessToken: session.ensureAccessToken,
  getOptionKeyword: () => optionSearchForm.departmentKeyword,
  getPinnedDepartments: () => [
    ...(session.currentUser.value?.departments ?? []),
    ...(runtime.selectedKnowledgeBaseDetail.value?.owner_department
      ? [runtime.selectedKnowledgeBaseDetail.value.owner_department]
      : []),
    ...(runtime.selectedKnowledgeBaseDetail.value?.default_document_owner_department
      ? [runtime.selectedKnowledgeBaseDetail.value.default_document_owner_department]
      : []),
  ],
  onDepartmentOptionsChanged: () => syncKnowledgeBaseCreateOwnerDefaultFromRuntime(),
  selectorPageSize,
});
const activeDepartments = computed(() =>
  adminDepartmentOptions.value.filter((department) => department.status === "active"),
);

const runtime = useKnowledgeAdminRuntime({
  activeDepartments,
  adminDepartmentOptions,
  adminDepartments,
  canImportDocuments: capabilities.canImportDocuments,
  canIndexDocuments: capabilities.canIndexDocuments,
  canLoadImportAdmin: capabilities.canLoadImportAdmin,
  canLoadIndexOps: capabilities.canLoadIndexOps,
  canManageDocuments: capabilities.canManageDocuments,
  canManageFolders: capabilities.canManageFolders,
  canManageKnowledgeBases: capabilities.canManageKnowledgeBases,
  canManagePermissions: capabilities.canManagePermissions,
  canReadDepartments: capabilities.canReadDepartments,
  canReadImportJobs: capabilities.canReadImportJobs,
  currentUser: session.currentUser,
  ensureAccessToken: session.ensureAccessToken,
  normalizeErrorMessage,
  optionSearchForm,
  refreshDepartmentOptions,
  refreshIndexHealth: async () => undefined,
  selectorPageSize,
  syncRoleBindingScopeDefault: () => undefined,
});
syncKnowledgeBaseCreateOwnerDefaultFromRuntime =
  runtime.syncKnowledgeBaseCreateOwnerDefault;

const displayLookups = useKnowledgeDisplayLookups({
  adminDepartmentOptions,
  adminDepartments,
  adminFolderOptions: runtime.adminFolderOptions,
  adminFolders: runtime.adminFolders,
  adminKnowledgeBaseOptions: runtime.adminKnowledgeBaseOptions,
  adminKnowledgeBases: runtime.adminKnowledgeBases,
  currentUser: session.currentUser,
  documentChunkPagination: runtime.documentChunkPagination,
  documentIndexVersionPagination: runtime.documentIndexVersionPagination,
  selectedDocumentId: runtime.selectedDocumentId,
  selectedDocumentVersions: runtime.selectedDocumentVersions,
  selectedKnowledgeBaseDetail: runtime.selectedKnowledgeBaseDetail,
});

const knowledgeAdminModel = createKnowledgeAdminContext({
  ...runtime,
  ...displayLookups,
  activeDepartments,
  adminDepartments,
  authenticated: session.authenticated,
  canImportDocuments: capabilities.canImportDocuments,
  canIndexDocuments: capabilities.canIndexDocuments,
  canLoadImportAdmin: capabilities.canLoadImportAdmin,
  canLoadIndexOps: capabilities.canLoadIndexOps,
  canManageDepartments: capabilities.canManageDepartments,
  canManageDocuments: capabilities.canManageDocuments,
  canManageFolders: capabilities.canManageFolders,
  canManageKnowledgeBases: capabilities.canManageKnowledgeBases,
  canManagePermissions: capabilities.canManagePermissions,
  canReadDepartments: capabilities.canReadDepartments,
  canReadImportJobs: capabilities.canReadImportJobs,
  changePaginationPage,
  changePaginationPageSize,
  currentUser: session.currentUser,
  documentIndexStatusTone,
  documentLifecycleStatusTone,
  documentVersionStatusTone,
  documentVisibilityLabel,
  folderStatusTone,
  formatAuditTime,
  formatChunkPageRange,
  formatDepartmentLabel,
  formatDepartmentList,
  formatDocumentCount,
  formatDocumentVersion,
  formatFileSize,
  formatFolderLabel,
  formatImportJobTitle,
  formatKnowledgeBaseLabel,
  formatStatusOption,
  formatStatusText,
  importJobStageLabel,
  importJobStatusTone,
  indexVersionStatusTone,
  knowledgeBaseStatusTone,
  knowledgeBaseVisibilityLabel,
  optionSearchForm,
  pageSizeOptions,
  paginationEnd,
  paginationStart,
  refreshDepartmentOptionsFromSearch,
  refreshFirstPage,
  toneClass,
  userRoleLabels: session.userRoleLabels,
});

onMounted(async () => {
  await runtime.refreshKnowledgeBaseAdminState();
});
</script>

<template>
  <KnowledgeBaseAdminContainer :model="knowledgeAdminModel" />
</template>
