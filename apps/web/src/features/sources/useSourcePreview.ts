import { computed, reactive, ref } from "vue";

import {
  getCitationSource,
  listDocumentChunks,
  type ChunkData,
  type CitationSourceData,
} from "@/api/documents";
import type { CitationData } from "@/api/query";

const SOURCE_CHUNK_PAGE_SIZE = 20;

type UseSourcePreviewOptions = {
  ensureAccessToken: () => Promise<string | null>;
  formatError: (error: unknown) => string;
};

export function useSourcePreview(options: UseSourcePreviewOptions) {
  const detail = ref<CitationSourceData | null>(null);
  const chunks = ref<ChunkData[]>([]);
  const pagination = reactive({
    page: 1,
    pageSize: SOURCE_CHUNK_PAGE_SIZE,
    total: 0,
  });
  const highlightedChunkId = ref("");
  const title = ref("");
  const documentId = ref("");
  const feedback = ref("");
  const loading = ref(false);
  const hasMore = computed(() => chunks.value.length < pagination.total);

  async function openCitation(citation: CitationData): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      feedback.value = "请先登录。";
      return;
    }
    loading.value = true;
    feedback.value = "";
    highlightedChunkId.value = citation.source_id;
    title.value = citation.title;
    documentId.value = citation.doc_id;
    detail.value = null;
    chunks.value = [];
    clearPagination();
    try {
      const response = await getCitationSource(citation.doc_id, citation.source_id, accessToken);
      detail.value = response.data;
    } catch (error) {
      feedback.value = options.formatError(error);
    } finally {
      loading.value = false;
    }
  }

  async function openDocument(
    targetDocumentId: string,
    targetTitle: string,
    targetSourceId = "",
  ): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken) {
      feedback.value = "请先登录。";
      return;
    }
    loading.value = true;
    feedback.value = "";
    highlightedChunkId.value = targetSourceId;
    title.value = targetTitle;
    documentId.value = targetDocumentId;
    detail.value = null;
    chunks.value = [];
    clearPagination();
    try {
      await loadDocumentChunksPage(targetDocumentId, accessToken, false);
    } catch (error) {
      chunks.value = [];
      feedback.value = options.formatError(error);
    } finally {
      loading.value = false;
    }
  }

  async function loadMore(): Promise<void> {
    const accessToken = await options.ensureAccessToken();
    if (!accessToken || !documentId.value || loading.value || !hasMore.value) {
      return;
    }
    loading.value = true;
    feedback.value = "";
    try {
      await loadDocumentChunksPage(documentId.value, accessToken, true);
    } catch (error) {
      feedback.value = options.formatError(error);
    } finally {
      loading.value = false;
    }
  }

  function reset(): void {
    detail.value = null;
    chunks.value = [];
    clearPagination();
    highlightedChunkId.value = "";
    title.value = "";
    documentId.value = "";
    feedback.value = "";
  }

  async function loadDocumentChunksPage(
    targetDocumentId: string,
    accessToken: string,
    append: boolean,
  ): Promise<void> {
    const nextPage = append ? pagination.page + 1 : 1;
    const response = await listDocumentChunks(targetDocumentId, accessToken, {
      page: nextPage,
      page_size: pagination.pageSize,
    });
    pagination.page = response.pagination.page;
    pagination.pageSize = response.pagination.page_size;
    pagination.total = response.pagination.total;
    if (append) {
      const existing = new Map(chunks.value.map((chunk) => [chunk.id, chunk]));
      for (const chunk of response.data) {
        existing.set(chunk.id, chunk);
      }
      chunks.value = Array.from(existing.values());
      return;
    }
    chunks.value = response.data;
  }

  function clearPagination(): void {
    pagination.page = 1;
    pagination.total = 0;
  }

  return {
    chunks,
    detail,
    feedback,
    hasMore,
    highlightedChunkId,
    loading,
    pagination,
    title,
    loadMore,
    openCitation,
    openDocument,
    reset,
  };
}
