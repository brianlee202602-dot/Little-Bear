<script setup lang="ts">
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import { formatAuditTime } from "@/utils/date";
import {
  formatLatency,
  formatStatusOption,
  formatStatusText,
} from "@/utils/display";
import {
  formatModelCallStatus,
  modelCallStatusTone,
} from "@/utils/status";
import {
  changePaginationPage,
  changePaginationPageSize,
  refreshFirstPage,
} from "@/utils/pagination";

const props = defineProps<{
  pageSizeOptions: number[];
  runtime: DiagnosticsRuntime;
}>();

const { pageSizeOptions } = props;
const {
  canLoadDiagnostics,
  diagnosticsBusy,
  modelCallLogPagination,
  modelCallLogs,
  modelCallSearchForm,
  openModelCallLogDetail,
  refreshModelCallLogs,
} = props.runtime;
</script>

<template>
  <section class="diagnostics-pane">
    <header class="resource-section__header">
      <div>
        <h4>模型调用日志</h4>
        <p>展示模型路由、调用方、耗时、token 摘要和错误码，不展示 prompt 或文档原文。</p>
      </div>
      <span>{{ diagnosticsBusy.loadingModelCallLogs ? "读取中" : `${modelCallLogPagination.total} 条` }}</span>
    </header>

    <ListFilter
      class="list-filter--model-calls"
      submit-label="查询调用"
      :submit-disabled="!canLoadDiagnostics || diagnosticsBusy.loadingModelCallLogs"
      @submit="refreshFirstPage(modelCallLogPagination, refreshModelCallLogs)"
    >
      <label class="field">
        <span class="field__label">Trace ID</span>
        <input v-model.trim="modelCallSearchForm.traceId" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">模型</span>
        <input v-model.trim="modelCallSearchForm.model" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">类型</span>
        <select v-model="modelCallSearchForm.modelType" class="control">
          <option value="">全部</option>
          <option value="llm">{{ formatStatusOption("llm") }}</option>
          <option value="rerank">{{ formatStatusOption("rerank") }}</option>
          <option value="embedding">{{ formatStatusOption("embedding") }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field__label">调用方</span>
        <input v-model.trim="modelCallSearchForm.caller" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">状态</span>
        <select v-model="modelCallSearchForm.status" class="control">
          <option value="">全部</option>
          <option value="success">{{ formatStatusOption("success") }}</option>
          <option value="failed">{{ formatStatusOption("failed") }}</option>
          <option value="degraded">{{ formatStatusOption("degraded") }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field__label">是否降级</span>
        <select v-model="modelCallSearchForm.degraded" class="control">
          <option value="">全部</option>
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      </label>
    </ListFilter>

    <div v-if="modelCallLogs.length" class="entity-table entity-table--model-calls">
      <div class="entity-table__row entity-table__row--header">
        <span>模型</span>
        <span>调用方</span>
        <span>状态</span>
        <span>耗时</span>
        <span>时间</span>
        <span>操作</span>
      </div>
      <article v-for="log in modelCallLogs" :key="log.id" class="entity-table__row">
        <div class="entity-main">
          <strong>{{ log.model_name }}</strong>
          <span>{{ formatStatusText(log.model_type) }} / {{ log.model_version ?? "-" }}</span>
        </div>
        <div class="entity-cell">{{ log.caller }}</div>
        <div class="entity-cell">
          <StatusBadge
            :label="formatModelCallStatus(log)"
            :tone="modelCallStatusTone(log)"
          />
        </div>
        <div class="entity-cell">{{ formatLatency(log.latency_ms) }}</div>
        <div class="entity-cell">{{ formatAuditTime(log.created_at) }}</div>
        <div class="row-actions row-actions--dense">
          <button
            class="button button--secondary button--small"
            type="button"
            @click="openModelCallLogDetail(log)"
            :disabled="diagnosticsBusy.loadingModelCallDetail"
          >
            详情
          </button>
        </div>
      </article>
    </div>
    <p v-else-if="canLoadDiagnostics" class="empty-state empty-state--plain">当前尚未读取到模型调用日志。</p>
    <PaginationBar
      v-if="modelCallLogPagination.total > 0"
      label="模型调用日志分页"
      :page="modelCallLogPagination.page"
      :page-size="modelCallLogPagination.pageSize"
      :total="modelCallLogPagination.total"
      :page-size-options="pageSizeOptions"
      :disabled="diagnosticsBusy.loadingModelCallLogs"
      @update:page="(page) => changePaginationPage(modelCallLogPagination, refreshModelCallLogs, page)"
      @update:page-size="(pageSize) => changePaginationPageSize(modelCallLogPagination, refreshModelCallLogs, pageSize)"
    />
  </section>
</template>
