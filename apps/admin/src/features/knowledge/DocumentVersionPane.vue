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
  documentVersionPagination,
  documentVersionStatusTone,
  formatDocumentVersion,
  formatStatusText,
  importAdminBusy,
  pageSizeOptions,
  paginationEnd,
  paginationStart,
  refreshSelectedDocumentVersions,
  selectedDocumentVersions,
} = props.model;
</script>

<template>
  <div class="document-detail-pane document-detail-pane--versions">
    <header class="document-detail-pane__header">
      <h4>文档版本</h4>
      <span>
        {{
          importAdminBusy.loadingDocumentVersions
            ? "读取中"
            : `${paginationStart(documentVersionPagination)}-${paginationEnd(documentVersionPagination)} / ${documentVersionPagination.total} 个版本`
        }}
      </span>
    </header>
    <div v-if="selectedDocumentVersions.length" class="document-version-list">
      <article v-for="version in selectedDocumentVersions" :key="version.id" class="document-version-row">
        <strong>{{ formatDocumentVersion(version) }}</strong>
        <StatusBadge
          :label="formatStatusText(version.status)"
          :tone="documentVersionStatusTone(version.status)"
        />
      </article>
    </div>
    <p v-else class="empty-state empty-state--plain">当前文档尚未读取到版本。</p>
    <PaginationBar
      v-if="documentVersionPagination.total > documentVersionPagination.pageSize"
      class="pagination-bar--compact"
      label="文档版本分页"
      :page="documentVersionPagination.page"
      :page-size="documentVersionPagination.pageSize"
      :total="documentVersionPagination.total"
      :page-size-options="pageSizeOptions"
      :disabled="importAdminBusy.loadingDocumentVersions"
      @update:page="
        (page) =>
          changePaginationPage(documentVersionPagination, () => refreshSelectedDocumentVersions(), page)
      "
      @update:page-size="
        (pageSize) =>
          changePaginationPageSize(
            documentVersionPagination,
            () => refreshSelectedDocumentVersions(),
            pageSize,
          )
      "
    />
  </div>
</template>
