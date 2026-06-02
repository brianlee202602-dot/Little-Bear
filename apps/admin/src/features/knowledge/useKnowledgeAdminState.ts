import { reactive, ref } from "vue";

import type { AdminDocumentListItemData } from "@/api/documents";
import type { AdminFolderData, AdminFolderOptionData } from "@/api/folders";
import type { ImportJobListItemData } from "@/api/imports";
import type {
  AdminKnowledgeBaseData,
  AdminKnowledgeBaseListItemData,
  AdminKnowledgeBaseOptionData,
} from "@/api/knowledgeBases";
import { useKnowledgeModals } from "@/features/knowledge/useKnowledgeModals";
import type { PaginationState } from "@/utils/pagination";
import type { Tone } from "@/utils/status";

export function useKnowledgeAdminState() {
  const importAdminBusy = reactive({
    loading: false,
    loadingFolders: false,
    loadingDocuments: false,
    loadingDocumentDetails: false,
    loadingDocumentVersions: false,
    creating: false,
    updating: false,
    deleting: false,
    managingFolder: false,
    uploading: false,
    updatingPermissions: false,
    loadingIndexVersions: false,
    rebuildingIndex: false,
    rebuildingBatchIndex: false,
    cleaningIndexVersions: false,
    loadingFailedIndexJobs: false,
    retryingIndexJobs: false,
  });
  const knowledgeBaseSearchForm = reactive({
    keyword: "",
    status: "",
  });
  const importSearchForm = reactive({
    kbId: "",
    jobType: "",
    status: "",
    stage: "",
  });
  const documentSearchForm = reactive({
    status: "",
  });
  const knowledgeBasePagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const folderPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const importJobPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const failedIndexJobPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const documentPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const documentVersionPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const documentIndexVersionPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 10,
    total: 0,
  });
  const documentChunkPagination = reactive<PaginationState>({
    page: 1,
    pageSize: 20,
    total: 0,
  });
  const modalState = useKnowledgeModals();
  const importAdminFeedback = ref<{
    tone: Exclude<Tone, "warning">;
    message: string;
  } | null>(null);
  const adminKnowledgeBases = ref<AdminKnowledgeBaseListItemData[]>([]);
  const adminKnowledgeBaseOptions = ref<AdminKnowledgeBaseOptionData[]>([]);
  const selectedKnowledgeBaseDetail = ref<AdminKnowledgeBaseData | null>(null);
  const adminFolders = ref<AdminFolderData[]>([]);
  const adminFolderOptions = ref<AdminFolderOptionData[]>([]);
  const adminDocuments = ref<AdminDocumentListItemData[]>([]);
  const adminImportJobs = ref<ImportJobListItemData[]>([]);
  const failedIndexJobs = ref<ImportJobListItemData[]>([]);
  const selectedFailedIndexJobIds = ref<string[]>([]);

  return {
    ...modalState,
    adminDocuments,
    adminFolderOptions,
    adminFolders,
    adminImportJobs,
    adminKnowledgeBaseOptions,
    adminKnowledgeBases,
    documentChunkPagination,
    documentIndexVersionPagination,
    documentPagination,
    documentSearchForm,
    documentVersionPagination,
    failedIndexJobPagination,
    failedIndexJobs,
    folderPagination,
    importAdminBusy,
    importAdminFeedback,
    importJobPagination,
    importSearchForm,
    knowledgeBasePagination,
    knowledgeBaseSearchForm,
    selectedFailedIndexJobIds,
    selectedKnowledgeBaseDetail,
  };
}
