<script setup lang="ts">
import type { KnowledgeBaseAdminContext } from "@/features/knowledge/knowledgeAdminContext";
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const props = defineProps<{
  model: KnowledgeBaseAdminContext;
}>();

const model = props.model;

const {
  activeKnowledgeBases,
  adminImportJobs,
  canIndexDocuments,
  canReadImportJobs,
  canRetrySelectedFailedIndexJobs,
  changePaginationPage,
  changePaginationPageSize,
  failedIndexJobDocumentCount,
  failedIndexJobPagination,
  failedIndexJobStageSummary,
  failedIndexJobs,
  formatDocumentCount,
  formatImportJobKnowledgeBase,
  formatImportJobTitle,
  formatKnowledgeBaseLabel,
  formatStatusOption,
  formatStatusText,
  importAdminBusy,
  importJobPagination,
  importJobStageLabel,
  importJobStatusTone,
  importSearchForm,
  indexRetryForm,
  onAllFailedIndexJobsToggle,
  onFailedIndexJobToggle,
  optionSearchForm,
  pageSizeOptions,
  paginationEnd,
  paginationStart,
  refreshFailedIndexJobs,
  refreshFailedIndexJobsPage,
  refreshImportTaskFilters,
  refreshKnowledgeBaseAdminState,
  refreshKnowledgeBaseOptionsFromSearch,
  retrySelectedFailedIndexJobs,
  selectedFailedIndexJobIds,
  selectedFailedIndexJobSet,
} = model;
</script>

<template>
      <ListFilter
        v-if="canReadImportJobs"
        class="list-filter list-filter--imports"
        submit-label="查询任务"
        :submit-disabled="importAdminBusy.loading"
        @submit="refreshImportTaskFilters"
      >
        <label class="field">
          <span class="field__label">任务所属知识库</span>
          <p class="field__hint">过滤导入、索引重建和权限刷新任务；这不是查询日志。</p>
          <div class="selector-search">
            <input
              v-model.trim="optionSearchForm.knowledgeBaseKeyword"
              class="control control--compact"
              type="search"
              placeholder="搜索知识库"
            />
            <button class="button button--secondary button--small" type="button" @click="refreshKnowledgeBaseOptionsFromSearch">
              查询知识库
            </button>
          </div>
          <select v-if="activeKnowledgeBases.length" v-model="importSearchForm.kbId" class="control">
            <option value="">全部</option>
            <option
              v-for="knowledgeBase in activeKnowledgeBases"
              :key="knowledgeBase.id"
              :value="knowledgeBase.id"
            >
              {{ formatKnowledgeBaseLabel(knowledgeBase) }}
            </option>
          </select>
          <input v-else v-model.trim="importSearchForm.kbId" class="control" type="text" />
        </label>
        <label class="field">
          <span class="field__label">状态</span>
          <p class="field__hint">按任务运行状态过滤。</p>
          <select v-model="importSearchForm.status" class="control">
            <option value="">全部</option>
            <option value="queued">{{ formatStatusOption("queued") }}</option>
            <option value="running">{{ formatStatusOption("running") }}</option>
            <option value="retrying">{{ formatStatusOption("retrying") }}</option>
            <option value="partial_success">{{ formatStatusOption("partial_success") }}</option>
            <option value="success">{{ formatStatusOption("success") }}</option>
            <option value="failed">{{ formatStatusOption("failed") }}</option>
            <option value="cancelled">{{ formatStatusOption("cancelled") }}</option>
          </select>
        </label>
        <label class="field">
          <span class="field__label">任务类型</span>
          <p class="field__hint">按导入或索引任务类型过滤。</p>
          <select v-model="importSearchForm.jobType" class="control">
            <option value="">全部</option>
            <option value="upload">{{ formatStatusOption("upload") }}</option>
            <option value="url">{{ formatStatusOption("url") }}</option>
            <option value="metadata_batch">{{ formatStatusOption("metadata_batch") }}</option>
            <option value="index_rebuild">{{ formatStatusOption("index_rebuild") }}</option>
            <option value="permission_refresh">{{ formatStatusOption("permission_refresh") }}</option>
          </select>
        </label>
        <label class="field">
          <span class="field__label">阶段</span>
          <p class="field__hint">按导入阶段过滤。</p>
          <select v-model="importSearchForm.stage" class="control">
            <option value="">全部</option>
            <option value="validate">{{ importJobStageLabel("validate") }}</option>
            <option value="parse">{{ importJobStageLabel("parse") }}</option>
            <option value="clean">{{ importJobStageLabel("clean") }}</option>
            <option value="chunk">{{ importJobStageLabel("chunk") }}</option>
            <option value="embed">{{ importJobStageLabel("embed") }}</option>
            <option value="index">{{ importJobStageLabel("index") }}</option>
            <option value="publish">{{ importJobStageLabel("publish") }}</option>
            <option value="cleanup">{{ importJobStageLabel("cleanup") }}</option>
            <option value="finished">{{ importJobStageLabel("finished") }}</option>
          </select>
        </label>
      </ListFilter>

      <section v-if="canReadImportJobs" class="resource-block">
        <header class="resource-section__header">
          <div>
            <h4>失败索引任务</h4>
            <p>
              {{ paginationStart(failedIndexJobPagination) }}-{{ paginationEnd(failedIndexJobPagination) }} /
              {{ failedIndexJobPagination.total }} 个失败任务，
              当前页 {{ failedIndexJobDocumentCount }} 个文档 /
              {{ failedIndexJobStageSummary.length ? failedIndexJobStageSummary.join("，") : "无失败阶段" }}
            </p>
          </div>
          <div class="panel__actions">
            <button
              class="button button--secondary button--small"
              type="button"
              @click="refreshFailedIndexJobs()"
              :disabled="importAdminBusy.loadingFailedIndexJobs"
            >
              {{ importAdminBusy.loadingFailedIndexJobs ? "刷新中" : "刷新失败任务" }}
            </button>
            <button
              class="button button--small"
              type="button"
              @click="retrySelectedFailedIndexJobs"
              :disabled="!canRetrySelectedFailedIndexJobs"
            >
              {{ importAdminBusy.retryingIndexJobs ? "创建中..." : "批量重试" }}
            </button>
          </div>
        </header>
        <label class="confirm confirm--inline">
          <input
            v-model="indexRetryForm.confirmedRetry"
            type="checkbox"
            :disabled="!selectedFailedIndexJobIds.length || !canIndexDocuments"
          />
          <span>确认重试选中的失败索引任务</span>
        </label>
        <div v-if="failedIndexJobs.length" class="entity-table entity-table--index-jobs">
          <div class="entity-table__row entity-table__row--header">
            <span>
              <input
                type="checkbox"
                :checked="selectedFailedIndexJobIds.length === failedIndexJobs.length"
                @change="onAllFailedIndexJobsToggle"
              />
            </span>
            <span>任务</span>
            <span>知识库</span>
            <span>阶段</span>
            <span>文档</span>
            <span>错误</span>
          </div>
          <article v-for="job in failedIndexJobs" :key="job.id" class="entity-table__row">
            <div class="entity-cell">
              <input
                type="checkbox"
                :checked="selectedFailedIndexJobSet.has(job.id)"
                @change="onFailedIndexJobToggle(job.id, $event)"
              />
            </div>
            <div class="entity-main">
              <strong>{{ formatImportJobTitle(job) }}</strong>
              <span>{{ formatStatusText(job.job_type) }}</span>
            </div>
            <div class="entity-cell">{{ formatImportJobKnowledgeBase(job) }}</div>
            <div class="entity-cell">{{ importJobStageLabel(job.stage) }}</div>
            <div class="entity-cell">{{ formatDocumentCount(job.document_count) }}</div>
            <div class="entity-cell">{{ job.error_summary ?? "-" }}</div>
          </article>
        </div>
        <p v-else class="empty-state empty-state--plain">当前没有失败的索引重建任务。</p>
        <PaginationBar
          v-if="failedIndexJobPagination.total > 0"
          label="失败索引任务分页"
          :page="failedIndexJobPagination.page"
          :page-size="failedIndexJobPagination.pageSize"
          :total="failedIndexJobPagination.total"
          :page-size-options="pageSizeOptions"
          :disabled="importAdminBusy.loadingFailedIndexJobs"
          @update:page="(page) => changePaginationPage(failedIndexJobPagination, refreshFailedIndexJobsPage, page)"
          @update:page-size="(pageSize) => changePaginationPageSize(failedIndexJobPagination, refreshFailedIndexJobsPage, pageSize)"
        />
      </section>

      <div v-if="canReadImportJobs && adminImportJobs.length" class="entity-table entity-table--imports">
        <div class="entity-table__row entity-table__row--header">
          <span>任务</span>
          <span>类型</span>
          <span>知识库</span>
          <span>状态</span>
          <span>阶段</span>
          <span>文档</span>
          <span>错误</span>
        </div>
        <article v-for="job in adminImportJobs" :key="job.id" class="entity-table__row">
          <div class="entity-main">
            <strong>{{ formatImportJobTitle(job) }}</strong>
            <span>{{ formatDocumentCount(job.document_count) }}</span>
          </div>
          <div class="entity-cell">{{ formatStatusText(job.job_type) }}</div>
          <div class="entity-cell">{{ formatImportJobKnowledgeBase(job) }}</div>
          <div class="entity-cell">
            <StatusBadge
              :label="formatStatusText(job.status)"
              :tone="importJobStatusTone(job.status)"
            />
          </div>
          <div class="entity-cell">{{ importJobStageLabel(job.stage) }}</div>
          <div class="entity-cell">{{ formatDocumentCount(job.document_count) }}</div>
          <div class="entity-cell">{{ job.error_summary ?? "-" }}</div>
        </article>
      </div>
      <p v-else-if="canReadImportJobs" class="empty-state empty-state--plain">当前尚未读取到导入任务。</p>
      <p v-else class="empty-state empty-state--plain">当前账号缺少 import_job:read，上传后只能看到本次创建结果。</p>
      <PaginationBar
        v-if="canReadImportJobs && importJobPagination.total > 0"
        label="知识库任务列表分页"
        :page="importJobPagination.page"
        :page-size="importJobPagination.pageSize"
        :total="importJobPagination.total"
        :page-size-options="pageSizeOptions"
        :disabled="importAdminBusy.loading"
        @update:page="(page) => changePaginationPage(importJobPagination, refreshKnowledgeBaseAdminState, page)"
        @update:page-size="(pageSize) => changePaginationPageSize(importJobPagination, refreshKnowledgeBaseAdminState, pageSize)"
      />
</template>
