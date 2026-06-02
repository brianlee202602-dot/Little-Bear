import type { AdminDocumentListItemData, IndexVersionData } from "@/api/documents";
import type { UseKnowledgeDocumentsDependencies } from "@/features/knowledge/useKnowledgeDocuments";

type UseKnowledgeDocumentLoadersDependencies = Pick<
  UseKnowledgeDocumentsDependencies,
  | "adminDocuments"
  | "canIndexDocuments"
  | "canManageDocuments"
  | "clearBatchDocumentSelection"
  | "clearIndexVersionCleanupSelection"
  | "clearPaginationState"
  | "clearSelectedDocumentDetails"
  | "documentChunkPagination"
  | "documentIndexForm"
  | "documentIndexVersionPagination"
  | "documentModalMode"
  | "documentPagination"
  | "documentPermissionForm"
  | "documentSearchForm"
  | "documentVersionPagination"
  | "ensureAccessToken"
  | "getAdminDocument"
  | "highlightedDocumentChunkId"
  | "importAdminBusy"
  | "importAdminFeedback"
  | "listAdminDocumentChunks"
  | "listAdminDocumentIndexVersions"
  | "listAdminDocuments"
  | "listAdminDocumentVersions"
  | "normalizeErrorMessage"
  | "paginationTotalPages"
  | "pruneSelectedBatchDocuments"
  | "pruneSelectedIndexVersionsForCleanup"
  | "selectedAdminDocumentDetail"
  | "selectedDocumentChunks"
  | "selectedDocumentId"
  | "selectedDocumentIndexVersions"
  | "selectedDocumentVersions"
  | "selectedKnowledgeBase"
  | "syncDocumentPermissionForm"
  | "syncPaginationState"
>;

export function useKnowledgeDocumentLoaders(options: UseKnowledgeDocumentLoadersDependencies) {
  const {
    adminDocuments,
    canIndexDocuments,
    canManageDocuments,
    clearBatchDocumentSelection,
    clearIndexVersionCleanupSelection,
    clearPaginationState,
    clearSelectedDocumentDetails,
    documentChunkPagination,
    documentIndexForm,
    documentIndexVersionPagination,
    documentModalMode,
    documentPagination,
    documentPermissionForm,
    documentSearchForm,
    documentVersionPagination,
    ensureAccessToken,
    getAdminDocument,
    highlightedDocumentChunkId,
    importAdminBusy,
    importAdminFeedback,
    listAdminDocumentChunks,
    listAdminDocumentIndexVersions,
    listAdminDocuments,
    listAdminDocumentVersions,
    normalizeErrorMessage,
    paginationTotalPages,
    pruneSelectedBatchDocuments,
    pruneSelectedIndexVersionsForCleanup,
    selectedAdminDocumentDetail,
    selectedDocumentChunks,
    selectedDocumentId,
    selectedDocumentIndexVersions,
    selectedDocumentVersions,
    selectedKnowledgeBase,
    syncDocumentPermissionForm,
    syncPaginationState,
  } = options;

  function clearSelectedDocumentMetadata(): void {
    selectedAdminDocumentDetail.value = null;
    syncDocumentPermissionForm();
  }

  async function refreshSelectedKnowledgeBaseDocuments(existingAccessToken?: string): Promise<void> {
    const knowledgeBase = selectedKnowledgeBase.value;
    if (!knowledgeBase || !canManageDocuments.value) {
      adminDocuments.value = [];
      selectedDocumentId.value = "";
      clearPaginationState(documentPagination);
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
      clearBatchDocumentSelection();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingDocuments = true;
    try {
      const response = await listAdminDocuments(knowledgeBase.id, accessToken, {
        status: documentSearchForm.status || undefined,
        page: documentPagination.page,
        page_size: documentPagination.pageSize,
      });
      adminDocuments.value = response.data;
      syncPaginationState(documentPagination, response.pagination);
      if (
        adminDocuments.value.length === 0 &&
        documentPagination.total > 0 &&
        documentPagination.page > 1
      ) {
        documentPagination.page = paginationTotalPages(documentPagination);
        await refreshSelectedKnowledgeBaseDocuments(accessToken);
        return;
      }
      pruneSelectedBatchDocuments();
      if (
        selectedDocumentId.value &&
        !adminDocuments.value.some((document: { id: string }) => document.id === selectedDocumentId.value)
      ) {
        selectedDocumentId.value = "";
        clearSelectedDocumentDetails();
        clearSelectedDocumentMetadata();
      }
      syncDocumentPermissionForm();
      if (selectedDocumentId.value && documentModalMode.value === "details") {
        await refreshSelectedDocumentDetails(accessToken);
      } else if (selectedDocumentId.value && documentModalMode.value === "permissions") {
        await refreshSelectedDocumentMetadata(accessToken);
      }
    } catch (error) {
      adminDocuments.value = [];
      selectedDocumentId.value = "";
      clearPaginationState(documentPagination);
      clearBatchDocumentSelection();
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取知识库文档失败"),
      };
    } finally {
      importAdminBusy.loadingDocuments = false;
    }
  }

  async function refreshSelectedDocumentDetails(existingAccessToken?: string): Promise<void> {
    const documentId = selectedDocumentId.value;
    if (!documentId || !canManageDocuments.value) {
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingDocumentDetails = true;
    importAdminBusy.loadingDocumentVersions = true;
    importAdminBusy.loadingIndexVersions = canIndexDocuments.value;
    try {
      const [documentResponse, versionsResponse, chunksResponse, indexVersionsResponse] =
        await Promise.all([
          getAdminDocument(documentId, accessToken),
          listAdminDocumentVersions(documentId, accessToken, {
            page: documentVersionPagination.page,
            page_size: documentVersionPagination.pageSize,
          }),
          listAdminDocumentChunks(documentId, accessToken, {
            page: documentChunkPagination.page,
            page_size: documentChunkPagination.pageSize,
          }),
          canIndexDocuments.value
            ? listAdminDocumentIndexVersions(documentId, accessToken, {
                page: documentIndexVersionPagination.page,
                page_size: documentIndexVersionPagination.pageSize,
              })
            : Promise.resolve({
                request_id: "",
                data: [] as IndexVersionData[],
                pagination: {
                  page: 1,
                  page_size: documentIndexVersionPagination.pageSize,
                  total: 0,
                },
              }),
        ]);
      selectedAdminDocumentDetail.value = documentResponse.data;
      selectedDocumentVersions.value = versionsResponse.data;
      syncPaginationState(documentVersionPagination, versionsResponse.pagination);
      selectedDocumentChunks.value = chunksResponse.data;
      syncPaginationState(documentChunkPagination, chunksResponse.pagination);
      selectedDocumentIndexVersions.value = indexVersionsResponse.data;
      syncPaginationState(documentIndexVersionPagination, indexVersionsResponse.pagination);
      highlightedDocumentChunkId.value = chunksResponse.data[0]?.id ?? "";
      documentIndexForm.confirmedRebuild = false;
      pruneSelectedIndexVersionsForCleanup();
      syncDocumentPermissionForm();
    } catch (error) {
      clearSelectedDocumentDetails();
      clearSelectedDocumentMetadata();
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取文档版本、chunk 或索引版本失败"),
      };
    } finally {
      importAdminBusy.loadingDocumentDetails = false;
      importAdminBusy.loadingDocumentVersions = false;
      importAdminBusy.loadingIndexVersions = false;
    }
  }

  async function refreshSelectedDocumentMetadata(existingAccessToken?: string): Promise<void> {
    const documentId = selectedDocumentId.value;
    if (!documentId || !canManageDocuments.value) {
      clearSelectedDocumentMetadata();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingDocumentDetails = true;
    try {
      const response = await getAdminDocument(documentId, accessToken);
      selectedAdminDocumentDetail.value = response.data;
      syncDocumentPermissionForm();
    } catch (error) {
      clearSelectedDocumentMetadata();
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取文档详情失败"),
      };
    } finally {
      importAdminBusy.loadingDocumentDetails = false;
    }
  }

  async function refreshSelectedDocumentVersions(existingAccessToken?: string): Promise<void> {
    const documentId = selectedDocumentId.value;
    if (!documentId || !canManageDocuments.value) {
      selectedDocumentVersions.value = [];
      clearPaginationState(documentVersionPagination);
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingDocumentVersions = true;
    try {
      const response = await listAdminDocumentVersions(documentId, accessToken, {
        page: documentVersionPagination.page,
        page_size: documentVersionPagination.pageSize,
      });
      selectedDocumentVersions.value = response.data;
      syncPaginationState(documentVersionPagination, response.pagination);
    } catch (error) {
      selectedDocumentVersions.value = [];
      clearPaginationState(documentVersionPagination);
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取文档版本失败"),
      };
    } finally {
      importAdminBusy.loadingDocumentVersions = false;
    }
  }

  async function refreshSelectedDocumentIndexVersions(existingAccessToken?: string): Promise<void> {
    const documentId = selectedDocumentId.value;
    if (!documentId || !canIndexDocuments.value) {
      selectedDocumentIndexVersions.value = [];
      clearPaginationState(documentIndexVersionPagination);
      clearIndexVersionCleanupSelection();
      return;
    }
    const accessToken = existingAccessToken ?? (await ensureAccessToken());
    if (!accessToken) {
      return;
    }

    importAdminBusy.loadingIndexVersions = true;
    try {
      const response = await listAdminDocumentIndexVersions(documentId, accessToken, {
        page: documentIndexVersionPagination.page,
        page_size: documentIndexVersionPagination.pageSize,
      });
      selectedDocumentIndexVersions.value = response.data;
      syncPaginationState(documentIndexVersionPagination, response.pagination);
      pruneSelectedIndexVersionsForCleanup();
    } catch (error) {
      selectedDocumentIndexVersions.value = [];
      clearPaginationState(documentIndexVersionPagination);
      clearIndexVersionCleanupSelection();
      importAdminFeedback.value = {
        tone: "error",
        message: normalizeErrorMessage(error, "读取文档索引版本失败"),
      };
    } finally {
      importAdminBusy.loadingIndexVersions = false;
    }
  }

  async function openDocumentDetailsModal(document: AdminDocumentListItemData): Promise<void> {
    selectedDocumentId.value = document.id;
    selectedAdminDocumentDetail.value = null;
    clearPaginationState(documentVersionPagination);
    clearPaginationState(documentIndexVersionPagination);
    clearPaginationState(documentChunkPagination);
    syncDocumentPermissionForm();
    documentModalMode.value = "details";
    await refreshSelectedDocumentDetails();
  }

  async function openDocumentPermissionsModal(document: AdminDocumentListItemData): Promise<void> {
    selectedDocumentId.value = document.id;
    selectedAdminDocumentDetail.value = null;
    clearPaginationState(documentVersionPagination);
    clearPaginationState(documentIndexVersionPagination);
    clearPaginationState(documentChunkPagination);
    clearSelectedDocumentDetails();
    syncDocumentPermissionForm();
    documentModalMode.value = "permissions";
    await refreshSelectedDocumentMetadata();
  }

  function closeDocumentModal(): void {
    documentModalMode.value = null;
    documentPermissionForm.confirmedReplace = false;
  }

  return {
    clearSelectedDocumentMetadata,
    closeDocumentModal,
    openDocumentDetailsModal,
    openDocumentPermissionsModal,
    refreshSelectedDocumentDetails,
    refreshSelectedDocumentIndexVersions,
    refreshSelectedDocumentMetadata,
    refreshSelectedDocumentVersions,
    refreshSelectedKnowledgeBaseDocuments,
  };
}
