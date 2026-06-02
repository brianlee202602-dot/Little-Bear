<script setup lang="ts">
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  changePaginationPage,
  changePaginationPageSize,
  documentChunkPagination,
  formatChunkOrdinal,
  formatChunkPageRange,
  formatStatusText,
  highlightedDocumentChunkId,
  importAdminBusy,
  pageSizeOptions,
  paginationEnd,
  paginationStart,
  refreshSelectedDocumentDetails,
  selectDocumentChunk,
  selectedDocumentChunks,
} = props.model;
</script>

<template>
  <section class="document-detail-pane document-detail-pane--chunks">
    <header class="document-detail-pane__header">
      <h4>Chunk 预览</h4>
      <span>
        {{
          importAdminBusy.loadingDocumentDetails
            ? "读取中"
            : `${paginationStart(documentChunkPagination)}-${paginationEnd(documentChunkPagination)} / ${documentChunkPagination.total} 个片段`
        }}
      </span>
    </header>
    <div v-if="selectedDocumentChunks.length" class="chunk-preview-list chunk-preview-list--table">
      <button
        v-for="(chunk, index) in selectedDocumentChunks"
        :key="chunk.id"
        class="chunk-preview-row chunk-preview-row--button"
        :class="{ 'chunk-preview-row--active': chunk.id === highlightedDocumentChunkId }"
        type="button"
        @click="selectDocumentChunk(chunk.id)"
      >
        <header>
          <strong>{{ formatChunkOrdinal(chunk, index) }}</strong>
          <StatusBadge
            :label="formatStatusText(chunk.status)"
            :tone="chunk.status === 'active' ? 'success' : 'neutral'"
          />
          <span>页码 {{ formatChunkPageRange(chunk) }}</span>
        </header>
        <p>{{ chunk.text_preview }}</p>
      </button>
    </div>
    <p v-else class="empty-state empty-state--plain">当前文档尚未读取到 chunk。</p>
    <PaginationBar
      v-if="documentChunkPagination.total > documentChunkPagination.pageSize"
      label="Chunk 预览分页"
      :page="documentChunkPagination.page"
      :page-size="documentChunkPagination.pageSize"
      :total="documentChunkPagination.total"
      :page-size-options="pageSizeOptions"
      :disabled="importAdminBusy.loadingDocumentDetails"
      @update:page="
        (page) => changePaginationPage(documentChunkPagination, () => refreshSelectedDocumentDetails(), page)
      "
      @update:page-size="
        (pageSize) =>
          changePaginationPageSize(
            documentChunkPagination,
            () => refreshSelectedDocumentDetails(),
            pageSize,
          )
      "
    />
  </section>
</template>
