<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import FolderManagerPanel from "@/features/knowledge/FolderManagerPanel.vue";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const model = props.model;

const {
  adminDocuments,
  allBatchRebuildEligibleDocumentsSelected,
  batchRebuildEligibleDocuments,
  canIndexDocuments,
  canManageDocuments,
  canManageFolders,
  canManagePermissions,
  canRebuildSelectedDocumentsIndex,
  changePaginationPage,
  changePaginationPageSize,
  closeKnowledgeBaseDocumentManagerModal,
  documentIndexForm,
  documentManagerModalOpen,
  documentPagination,
  documentSearchForm,
  documentVisibilityLabel,
  formatDocumentCurrentVersion,
  formatKnowledgeBaseLabel,
  formatStatusOption,
  formatStatusText,
  importAdminBusy,
  isDocumentBatchRebuildEligible,
  onAllBatchDocumentsToggle,
  onBatchDocumentSelectionToggle,
  openDocumentDetailsModal,
  openDocumentPermissionsModal,
  pageSizeOptions,
  refreshFirstPage,
  refreshSelectedKnowledgeBaseDocuments,
  rebuildSelectedDocumentsIndex,
  selectedBatchDocumentSet,
  selectedBatchRebuildDocumentIds,
  selectedDocumentId,
  selectedKnowledgeBase,
  documentLifecycleStatusTone,
  documentIndexStatusTone,
} = props.model;
</script>

<template>
      <div
        v-if="documentManagerModalOpen"
        class="modal-backdrop"
        role="presentation"
        @click.self="closeKnowledgeBaseDocumentManagerModal"
      >
        <section class="modal modal--workspace" role="dialog" aria-modal="true" aria-labelledby="document-manager-modal-title">
          <header class="modal__header">
            <div>
              <p class="eyebrow">知识库管理</p>
              <h3 id="document-manager-modal-title">文档管理</h3>
              <p>{{ selectedKnowledgeBase ? formatKnowledgeBaseLabel(selectedKnowledgeBase) : "请选择知识库" }}</p>
            </div>
            <button class="button button--secondary button--small" type="button" @click="closeKnowledgeBaseDocumentManagerModal">
              关闭
            </button>
          </header>
          <div class="modal__body modal__body--documents">
            <section
              v-if="selectedKnowledgeBase && (canManageFolders || canManageDocuments)"
              class="resource-section resource-section--document-manager"
            >
        <FolderManagerPanel :model="model" />

        <section v-if="canManageDocuments" class="resource-block">
          <header class="resource-section__header">
            <div>
              <h4>文档管理</h4>
              <p>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</p>
            </div>
            <div class="panel__actions">
              <span v-if="canIndexDocuments">
                已选 {{ selectedBatchRebuildDocumentIds.length }} / 可重建 {{ batchRebuildEligibleDocuments.length }}
              </span>
              <button
                class="button button--secondary button--small"
                type="button"
                @click="refreshSelectedKnowledgeBaseDocuments()"
                :disabled="importAdminBusy.loadingDocuments"
              >
                {{ importAdminBusy.loadingDocuments ? "刷新中" : "刷新文档" }}
              </button>
            </div>
          </header>

          <ListFilter
            class="list-filter--documents"
            submit-label="查询文档"
            :submit-disabled="importAdminBusy.loadingDocuments"
            @submit="refreshFirstPage(documentPagination, refreshSelectedKnowledgeBaseDocuments)"
          >
            <label class="field">
              <span class="field__label">文档状态</span>
              <p class="field__hint">留空时显示当前知识库下全部未删除文档。</p>
              <select v-model="documentSearchForm.status" class="control">
                <option value="">全部</option>
                <option value="draft">{{ formatStatusOption("draft") }}</option>
                <option value="active">{{ formatStatusOption("active") }}</option>
                <option value="archived">{{ formatStatusOption("archived") }}</option>
              </select>
            </label>
          </ListFilter>

          <div v-if="canIndexDocuments" class="batch-action-bar">
            <label class="confirm confirm--inline">
              <input
                v-model="documentIndexForm.confirmedBatchRebuild"
                type="checkbox"
                :disabled="selectedBatchRebuildDocumentIds.length === 0"
              />
              <span>确认重建选中文档索引</span>
            </label>
            <button
              class="button"
              type="button"
              @click="rebuildSelectedDocumentsIndex"
              :disabled="!canRebuildSelectedDocumentsIndex"
            >
              {{ importAdminBusy.rebuildingBatchIndex ? "创建中..." : "批量重建索引" }}
            </button>
          </div>

          <div
            v-if="adminDocuments.length"
            :class="[
              'entity-table',
              'entity-table--documents',
              { 'entity-table--documents-selectable': canIndexDocuments },
            ]"
          >
            <div class="entity-table__row entity-table__row--header">
              <span v-if="canIndexDocuments">
                <input
                  type="checkbox"
                  :checked="allBatchRebuildEligibleDocumentsSelected"
                  :disabled="batchRebuildEligibleDocuments.length === 0"
                  @change="onAllBatchDocumentsToggle"
                />
              </span>
              <span>文档</span>
              <span>文件夹</span>
              <span>生命周期</span>
              <span>索引</span>
              <span>可见性</span>
              <span>当前版本</span>
              <span>操作</span>
            </div>
            <article
              v-for="document in adminDocuments"
              :key="document.id"
              :class="['entity-table__row', { 'entity-table__row--selected': document.id === selectedDocumentId }]"
            >
              <div v-if="canIndexDocuments" class="entity-cell">
                <input
                  type="checkbox"
                  :checked="selectedBatchDocumentSet.has(document.id)"
                  :disabled="!isDocumentBatchRebuildEligible(document)"
                  @change="onBatchDocumentSelectionToggle(document.id, $event)"
                />
              </div>
              <div class="entity-main">
                <strong>{{ document.title || "未命名文档" }}</strong>
              </div>
              <div class="entity-cell">{{ document.folder_name ?? "-" }}</div>
              <div class="entity-cell">
                <StatusBadge
                  :label="formatStatusText(document.lifecycle_status)"
                  :tone="documentLifecycleStatusTone(document.lifecycle_status)"
                />
              </div>
              <div class="entity-cell">
                <StatusBadge
                  :label="formatStatusText(document.index_status)"
                  :tone="documentIndexStatusTone(document.index_status)"
                />
              </div>
              <div class="entity-cell">
                {{ documentVisibilityLabel(document.visibility) }} /
                {{ document.owner_department_name ?? "-" }}
              </div>
              <div class="entity-cell">{{ formatDocumentCurrentVersion(document) }}</div>
              <div class="row-actions row-actions--dense">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  @click="openDocumentDetailsModal(document)"
                  :disabled="importAdminBusy.loadingDocumentDetails"
                >
                  版本与片段
                </button>
                <button
                  class="button button--secondary button--small"
                  type="button"
                  @click="openDocumentPermissionsModal(document)"
                  :disabled="!canManagePermissions"
                >
                  权限
                </button>
              </div>
            </article>
          </div>
          <p v-else class="empty-state empty-state--plain">当前知识库尚未读取到文档。</p>
          <PaginationBar
            v-if="documentPagination.total > 0"
            label="文档列表分页"
            :page="documentPagination.page"
            :page-size="documentPagination.pageSize"
            :total="documentPagination.total"
            :page-size-options="pageSizeOptions"
            :disabled="importAdminBusy.loadingDocuments"
            @update:page="(page) => changePaginationPage(documentPagination, () => refreshSelectedKnowledgeBaseDocuments(), page)"
            @update:page-size="(pageSize) => changePaginationPageSize(documentPagination, () => refreshSelectedKnowledgeBaseDocuments(), pageSize)"
          />

        </section>

        <p v-else class="empty-state empty-state--plain">
          当前账号缺少 document:manage，无法查看该知识库下的文档管理数据。
        </p>
            </section>
            <p v-else-if="selectedKnowledgeBase" class="empty-state empty-state--plain">
              当前账号缺少 folder:manage 和 document:manage，无法查看该知识库下的文件夹或文档管理数据。
            </p>
            <p v-else class="empty-state empty-state--plain">请选择一个知识库查看文档管理数据。</p>
          </div>
          <footer class="modal__footer">
            <button class="button button--secondary" type="button" @click="closeKnowledgeBaseDocumentManagerModal">
              关闭
            </button>
          </footer>
        </section>
      </div>


</template>
