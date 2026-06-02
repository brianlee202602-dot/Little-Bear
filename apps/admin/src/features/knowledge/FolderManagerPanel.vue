<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const {
  adminFolders,
  canManageFolders,
  changePaginationPage,
  changePaginationPageSize,
  folderPagination,
  folderStatusTone,
  formatFolderById,
  formatFolderLabel,
  formatKnowledgeBaseLabel,
  formatStatusText,
  importAdminBusy,
  openCreateFolderModal,
  openDeleteFolderModal,
  openEditFolderModal,
  pageSizeOptions,
  refreshSelectedKnowledgeBaseFolders,
  selectedFolderId,
  selectedKnowledgeBase,
} = props.model;
</script>

<template>
        <section v-if="canManageFolders" class="resource-block">
          <header class="resource-section__header">
            <div>
              <h4>文件夹管理</h4>
              <p>{{ formatKnowledgeBaseLabel(selectedKnowledgeBase) }}</p>
            </div>
            <div class="panel__actions">
              <button
                class="button button--secondary button--small"
                type="button"
                @click="refreshSelectedKnowledgeBaseFolders()"
                :disabled="importAdminBusy.loadingFolders"
              >
                {{ importAdminBusy.loadingFolders ? "刷新中" : "刷新文件夹" }}
              </button>
              <button class="button button--small" type="button" @click="openCreateFolderModal">
                新增文件夹
              </button>
            </div>
          </header>

          <div v-if="adminFolders.length" class="entity-table entity-table--folders">
            <div class="entity-table__row entity-table__row--header">
              <span>文件夹</span>
              <span>状态</span>
              <span>上级</span>
              <span>操作</span>
            </div>
            <article
              v-for="folder in adminFolders"
              :key="folder.id"
              :class="['entity-table__row', { 'entity-table__row--selected': folder.id === selectedFolderId }]"
            >
              <div class="entity-main">
                <strong>{{ formatFolderLabel(folder) }}</strong>
              </div>
              <div class="entity-cell">
                <StatusBadge
                  :label="formatStatusText(folder.status)"
                  :tone="folderStatusTone(folder.status)"
                />
              </div>
              <div class="entity-cell">{{ formatFolderById(folder.parent_id) }}</div>
              <div class="row-actions row-actions--dense">
                <button
                  class="button button--secondary button--small"
                  type="button"
                  @click="openEditFolderModal(folder)"
                >
                  编辑
                </button>
                <button
                  class="button button--danger button--small"
                  type="button"
                  @click="openDeleteFolderModal(folder)"
                >
                  删除
                </button>
              </div>
            </article>
          </div>
          <p v-else class="empty-state empty-state--plain">当前知识库尚未创建文件夹。</p>
          <PaginationBar
            v-if="folderPagination.total > 0"
            label="文件夹列表分页"
            :page="folderPagination.page"
            :page-size="folderPagination.pageSize"
            :total="folderPagination.total"
            :page-size-options="pageSizeOptions"
            :disabled="importAdminBusy.loadingFolders"
            @update:page="(page) => changePaginationPage(folderPagination, () => refreshSelectedKnowledgeBaseFolders(), page)"
            @update:page-size="(pageSize) => changePaginationPageSize(folderPagination, () => refreshSelectedKnowledgeBaseFolders(), pageSize)"
          />
        </section>

        <p v-else class="empty-state empty-state--plain">
          当前账号缺少 folder:manage，无法管理该知识库下的文件夹。
        </p>


</template>
