<script setup lang="ts">
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  allCleanupEligibleIndexVersionsSelected,
  canCleanupSelectedIndexVersions,
  canIndexDocuments,
  canRebuildSelectedDocumentIndex,
  changePaginationPage,
  changePaginationPageSize,
  cleanupEligibleIndexVersions,
  cleanupSelectedIndexVersions,
  documentIndexForm,
  documentIndexVersionPagination,
  formatAuditTime,
  formatIndexVersionLabel,
  formatStatusText,
  importAdminBusy,
  indexVersionStatusTone,
  onAllIndexVersionsForCleanupToggle,
  onIndexVersionCleanupSelectionToggle,
  pageSizeOptions,
  paginationEnd,
  paginationStart,
  rebuildSelectedDocumentIndex,
  refreshSelectedDocumentIndexVersions,
  selectedCleanupIndexVersionSet,
  selectedCleanupPendingDeleteIndexVersionIds,
  selectedDocumentIndexVersions,
} = props.model;
</script>

<template>
  <div class="document-detail-pane document-detail-pane--index">
    <header class="document-detail-pane__header">
      <div>
        <h4>索引版本</h4>
        <p>
          {{
            importAdminBusy.loadingIndexVersions
              ? "读取中"
              : `${paginationStart(documentIndexVersionPagination)}-${paginationEnd(documentIndexVersionPagination)} / ${documentIndexVersionPagination.total} 个索引版本`
          }}
        </p>
      </div>
      <button
        class="button button--secondary button--small"
        type="button"
        @click="refreshSelectedDocumentIndexVersions()"
        :disabled="!canIndexDocuments || importAdminBusy.loadingIndexVersions"
      >
        {{ importAdminBusy.loadingIndexVersions ? "刷新中" : "刷新索引" }}
      </button>
    </header>
    <p v-if="!canIndexDocuments" class="empty-state empty-state--plain">
      当前账号缺少 document:index，无法查看或重建索引。
    </p>
    <template v-else>
      <div v-if="cleanupEligibleIndexVersions.length" class="batch-action-bar">
        <label class="confirm confirm--inline">
          <input
            type="checkbox"
            :checked="allCleanupEligibleIndexVersionsSelected"
            @change="onAllIndexVersionsForCleanupToggle"
          />
          <span>
            已选 {{ selectedCleanupPendingDeleteIndexVersionIds.length }} /
            可清理 {{ cleanupEligibleIndexVersions.length }}
          </span>
        </label>
        <label class="confirm confirm--inline">
          <input
            v-model="documentIndexForm.confirmedCleanup"
            type="checkbox"
            :disabled="selectedCleanupPendingDeleteIndexVersionIds.length === 0"
          />
          <span>确认清理选中索引版本</span>
        </label>
        <button
          class="button button--secondary button--small"
          type="button"
          @click="cleanupSelectedIndexVersions"
          :disabled="!canCleanupSelectedIndexVersions"
        >
          {{ importAdminBusy.cleaningIndexVersions ? "创建中..." : "清理索引" }}
        </button>
      </div>
      <div v-if="selectedDocumentIndexVersions.length" class="index-version-list">
        <article
          v-for="(version, index) in selectedDocumentIndexVersions"
          :key="version.id"
          :class="[
            'index-version-row',
            { 'index-version-row--selectable': version.status === 'pending_delete' },
          ]"
        >
          <input
            v-if="version.status === 'pending_delete'"
            class="index-version-row__selector"
            type="checkbox"
            :checked="selectedCleanupIndexVersionSet.has(version.id)"
            @change="onIndexVersionCleanupSelectionToggle(version.id, $event)"
          />
          <div class="index-version-row__body">
            <header>
              <strong>{{ formatIndexVersionLabel(index) }}</strong>
              <StatusBadge
                :label="formatStatusText(version.status)"
                :tone="indexVersionStatusTone(version.status)"
              />
            </header>
            <dl>
              <div>
                <dt>模型</dt>
                <dd>{{ version.embedding_model }} / {{ version.model_version }}</dd>
              </div>
              <div>
                <dt>维度</dt>
                <dd>{{ version.dimension }}</dd>
              </div>
              <div>
                <dt>片段</dt>
                <dd>{{ version.chunk_count }}</dd>
              </div>
              <div>
                <dt>集合</dt>
                <dd>{{ version.collection_name }}</dd>
              </div>
              <div>
                <dt>创建</dt>
                <dd>{{ formatAuditTime(version.created_at) }}</dd>
              </div>
              <div>
                <dt>激活</dt>
                <dd>{{ formatAuditTime(version.activated_at) }}</dd>
              </div>
            </dl>
          </div>
        </article>
      </div>
      <p v-else class="empty-state empty-state--plain">当前文档尚未读取到索引版本。</p>
      <PaginationBar
        v-if="documentIndexVersionPagination.total > documentIndexVersionPagination.pageSize"
        class="pagination-bar--compact"
        label="索引版本分页"
        :page="documentIndexVersionPagination.page"
        :page-size="documentIndexVersionPagination.pageSize"
        :total="documentIndexVersionPagination.total"
        :page-size-options="pageSizeOptions"
        :disabled="importAdminBusy.loadingIndexVersions"
        @update:page="
          (page) =>
            changePaginationPage(
              documentIndexVersionPagination,
              () => refreshSelectedDocumentIndexVersions(),
              page,
            )
        "
        @update:page-size="
          (pageSize) =>
            changePaginationPageSize(
              documentIndexVersionPagination,
              () => refreshSelectedDocumentIndexVersions(),
              pageSize,
            )
        "
      />
      <div class="index-rebuild-panel">
        <label class="confirm confirm--inline">
          <input v-model="documentIndexForm.confirmedRebuild" type="checkbox" />
          <span>确认为当前文档重建索引</span>
        </label>
        <button
          class="button button--secondary button--small"
          type="button"
          @click="rebuildSelectedDocumentIndex"
          :disabled="!canRebuildSelectedDocumentIndex"
        >
          {{ importAdminBusy.rebuildingIndex ? "创建中..." : "重建索引" }}
        </button>
      </div>
    </template>
  </div>
</template>
