<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DocumentManagerModal from "@/features/knowledge/DocumentManagerModal.vue";
import KnowledgeImportTaskSection from "@/features/knowledge/KnowledgeImportTaskSection.vue";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const model = props.model;

const {
  activeDepartments,
  selectedFolderId,
  selectedDocumentId,
  refreshKnowledgeBaseOptionsFromSearch,
  refreshFailedIndexJobs,
  paginationStart,
  paginationEnd,
  optionSearchForm,
  knowledgeBaseStatusTone,
  indexRetryForm,
  formatStatusOption,
  formatKnowledgeBaseLabel,
  folderStatusTone,
  documentLifecycleStatusTone,
  documentIndexStatusTone,
  activeKnowledgeBases,
  adminDocuments,
  adminFolders,
  adminImportJobs,
  adminKnowledgeBases,
  allBatchRebuildEligibleDocumentsSelected,
  batchRebuildEligibleDocuments,
  canImportDocuments,
  canIndexDocuments,
  canLoadImportAdmin,
  canManageDocuments,
  canManageFolders,
  canManageKnowledgeBases,
  canManagePermissions,
  canReadImportJobs,
  canRebuildSelectedDocumentsIndex,
  canRetrySelectedFailedIndexJobs,
  changePaginationPage,
  changePaginationPageSize,
  documentIndexForm,
  documentPagination,
  documentSearchForm,
  failedIndexJobDocumentCount,
  failedIndexJobPagination,
  failedIndexJobStageSummary,
  failedIndexJobs,
  folderPagination,
  formatDepartmentById,
  formatDocumentCount,
  formatDocumentCurrentVersion,
  formatFolderById,
  formatFolderLabel,
  formatImportJobKnowledgeBase,
  formatImportJobTitle,
  formatStatusText,
  importAdminBusy,
  importAdminFeedback,
  importJobPagination,
  importJobStageLabel,
  importJobStatusTone,
  importSearchForm,
  isDocumentBatchRebuildEligible,
  knowledgeBasePagination,
  knowledgeBaseSearchForm,
  knowledgeBaseVisibilityLabel,
  documentVisibilityLabel,
  onAllBatchDocumentsToggle,
  onAllFailedIndexJobsToggle,
  onBatchDocumentSelectionToggle,
  onFailedIndexJobToggle,
  openCreateFolderModal,
  openCreateKnowledgeBaseModal,
  openDeleteFolderModal,
  openDeleteKnowledgeBaseModal,
  openDocumentDetailsModal,
  openDocumentPermissionsModal,
  openEditFolderModal,
  openEditKnowledgeBaseModal,
  openKnowledgeBaseDocumentManagerModal,
  openKnowledgeBasePermissionsModal,
  openRebuildKnowledgeBaseIndexModal,
  openUploadKnowledgeBaseModal,
  pageSizeOptions,
  refreshFailedIndexJobsPage,
  refreshFirstPage,
  refreshImportTaskFilters,
  refreshKnowledgeBaseAdminState,
  refreshSelectedKnowledgeBaseDocuments,
  refreshSelectedKnowledgeBaseFolders,
  rebuildSelectedDocumentsIndex,
  retrySelectedFailedIndexJobs,
  selectedBatchDocumentSet,
  selectedBatchRebuildDocumentIds,
  selectedFailedIndexJobIds,
  selectedFailedIndexJobSet,
  selectedKnowledgeBase,
  toneClass,
  closeKnowledgeBaseDocumentManagerModal,
  documentManagerModalOpen,
  formatAuditTime,
} = model;
</script>

<template>
  <section class="panel panel--wide">
    <header class="panel__header">
      <div>
        <h3>知识库管理</h3>
        <p :class="toneClass(canLoadImportAdmin ? 'success' : 'warning')">
          {{
            canManageKnowledgeBases
              ? "可管理知识库并添加文档"
              : canImportDocuments
                ? "可向指定知识库添加文档"
                : canReadImportJobs
                  ? "可读取导入任务"
                  : "缺少知识库或导入权限"
          }}
        </p>
      </div>
      <div class="panel__actions">
        <button
          class="button button--secondary"
          type="button"
          @click="refreshKnowledgeBaseAdminState"
          :disabled="importAdminBusy.loading || !canLoadImportAdmin"
        >
          {{ importAdminBusy.loading ? "刷新中" : "刷新知识库" }}
        </button>
        <button
          class="button"
          type="button"
          @click="openCreateKnowledgeBaseModal"
          :disabled="!canManageKnowledgeBases"
        >
          新增知识库
        </button>
      </div>
    </header>

    <div class="admin-list-panel">
      <div
        v-if="importAdminFeedback"
        :class="['feedback feedback--wide', `feedback--${importAdminFeedback.tone}`]"
      >
        {{ importAdminFeedback.message }}
      </div>

      <ListFilter
        class="list-filter--knowledge"
        :submit-disabled="importAdminBusy.loading"
        @submit="refreshFirstPage(knowledgeBasePagination, refreshKnowledgeBaseAdminState)"
      >
        <label class="field">
          <span class="field__label">关键词</span>
          <p class="field__hint">按知识库名称过滤。</p>
          <input v-model.trim="knowledgeBaseSearchForm.keyword" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">知识库状态</span>
          <p class="field__hint">留空时显示全部未删除知识库。</p>
          <select v-model="knowledgeBaseSearchForm.status" class="control">
            <option value="">全部</option>
            <option value="active">{{ formatStatusOption("active") }}</option>
            <option value="disabled">{{ formatStatusOption("disabled") }}</option>
            <option value="archived">{{ formatStatusOption("archived") }}</option>
          </select>
        </label>
      </ListFilter>

      <div v-if="canManageKnowledgeBases && adminKnowledgeBases.length" class="entity-table entity-table--knowledge">
        <div class="entity-table__row entity-table__row--header">
          <span>知识库</span>
          <span>状态</span>
          <span>可见性</span>
          <span>所属部门</span>
          <span>操作</span>
        </div>
        <article v-for="knowledgeBase in adminKnowledgeBases" :key="knowledgeBase.id" class="entity-table__row">
          <div class="entity-main">
            <strong>{{ knowledgeBase.name }}</strong>
          </div>
          <div class="entity-cell">
            <StatusBadge
              :label="formatStatusText(knowledgeBase.status)"
              :tone="knowledgeBaseStatusTone(knowledgeBase.status)"
            />
          </div>
          <div class="entity-cell">
            {{ knowledgeBaseVisibilityLabel(knowledgeBase.kb_visibility) }} /
            默认文档{{ documentVisibilityLabel(knowledgeBase.default_document_visibility) }}
          </div>
          <div class="entity-cell">{{ formatDepartmentById(knowledgeBase.owner_department_id) }}</div>
          <div class="row-actions row-actions--dense">
            <button
              class="button button--secondary button--small"
              type="button"
              @click="openKnowledgeBaseDocumentManagerModal(knowledgeBase)"
              :disabled="!canManageDocuments || importAdminBusy.loadingDocuments"
            >
              文档
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              @click="openUploadKnowledgeBaseModal(knowledgeBase)"
              :disabled="!canImportDocuments || knowledgeBase.status !== 'active'"
            >
              添加文件
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              @click="openKnowledgeBasePermissionsModal(knowledgeBase)"
              :disabled="!canManagePermissions"
            >
              权限
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              @click="openRebuildKnowledgeBaseIndexModal(knowledgeBase)"
              :disabled="!canIndexDocuments || knowledgeBase.status !== 'active'"
            >
              重建索引
            </button>
            <button
              class="button button--secondary button--small"
              type="button"
              @click="openEditKnowledgeBaseModal(knowledgeBase)"
              :disabled="!canManageKnowledgeBases"
            >
              编辑
            </button>
            <button
              class="button button--danger button--small"
              type="button"
              @click="openDeleteKnowledgeBaseModal(knowledgeBase)"
              :disabled="!canManageKnowledgeBases"
            >
              删除
            </button>
          </div>
        </article>
      </div>
      <p v-else-if="canManageKnowledgeBases" class="empty-state empty-state--plain">
        当前尚未读取到知识库。
      </p>
      <p v-else class="empty-state empty-state--plain">
        当前账号缺少 knowledge_base:manage，无法读取知识库列表；如需上传，请使用具备知识库管理权限的账号。
      </p>
      <PaginationBar
        v-if="canManageKnowledgeBases && knowledgeBasePagination.total > 0"
        label="知识库列表分页"
        :page="knowledgeBasePagination.page"
        :page-size="knowledgeBasePagination.pageSize"
        :total="knowledgeBasePagination.total"
        :page-size-options="pageSizeOptions"
        :disabled="importAdminBusy.loading"
        @update:page="(page) => changePaginationPage(knowledgeBasePagination, refreshKnowledgeBaseAdminState, page)"
        @update:page-size="(pageSize) => changePaginationPageSize(knowledgeBasePagination, refreshKnowledgeBaseAdminState, pageSize)"
      />

      <DocumentManagerModal :model="model" />

      <KnowledgeImportTaskSection :model="model" />
    </div>
  </section>
</template>
