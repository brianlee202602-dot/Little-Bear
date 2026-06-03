<script setup lang="ts">
import ListFilter from "@/components/ListFilter.vue";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import { formatAuditTime } from "@/utils/date";
import { formatLatency, formatStatusOption } from "@/utils/display";
import {
  formatDiagnosticReasonList,
  formatQueryLogKnowledgeBases,
  formatQueryLogStatus,
  formatQueryLogUser,
  queryLogStatusTone,
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
  queryLogPagination,
  queryLogs,
  queryLogSearchForm,
  refreshQueryLogs,
  selectQueryLog,
} = props.runtime;

function formatQueryScopeMode(value: string): string {
  return value === "auto_all_accessible" ? "自动范围" : "指定范围";
}
</script>

<template>
  <section class="diagnostics-pane">
    <header class="resource-section__header">
      <div>
        <h4>查询日志</h4>
        <p>按 request、trace、用户、知识库和降级原因定位一次问答。</p>
      </div>
      <span>{{ diagnosticsBusy.loadingQueryLogs ? "读取中" : `${queryLogPagination.total} 条` }}</span>
    </header>

    <ListFilter
      class="list-filter--diagnostics"
      :submit-disabled="!canLoadDiagnostics || diagnosticsBusy.loadingQueryLogs"
      @submit="refreshFirstPage(queryLogPagination, refreshQueryLogs)"
    >
      <label class="field">
        <span class="field__label">Trace ID</span>
        <input v-model.trim="queryLogSearchForm.traceId" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">Request ID</span>
        <input v-model.trim="queryLogSearchForm.requestId" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">用户 ID</span>
        <input v-model.trim="queryLogSearchForm.userId" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">知识库 ID</span>
        <input v-model.trim="queryLogSearchForm.kbId" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">状态</span>
        <select v-model="queryLogSearchForm.status" class="control">
          <option value="">全部</option>
          <option value="success">{{ formatStatusOption("success") }}</option>
          <option value="failed">{{ formatStatusOption("failed") }}</option>
          <option value="denied">{{ formatStatusOption("denied") }}</option>
        </select>
      </label>
      <label class="field">
        <span class="field__label">查询范围</span>
        <select v-model="queryLogSearchForm.queryScopeMode" class="control">
          <option value="">全部</option>
          <option value="auto_all_accessible">自动范围</option>
          <option value="explicit">指定范围</option>
        </select>
      </label>
      <label class="field">
        <span class="field__label">是否降级</span>
        <select v-model="queryLogSearchForm.degraded" class="control">
          <option value="">全部</option>
          <option value="true">是</option>
          <option value="false">否</option>
        </select>
      </label>
      <label class="field">
        <span class="field__label">降级原因</span>
        <input v-model.trim="queryLogSearchForm.degradeReason" class="control" type="text" />
      </label>
      <label class="field">
        <span class="field__label">错误码</span>
        <input v-model.trim="queryLogSearchForm.errorCode" class="control" type="text" />
      </label>
    </ListFilter>

    <div v-if="queryLogs.length" class="entity-table entity-table--query-logs">
      <div class="entity-table__row entity-table__row--header">
        <span>请求</span>
        <span>状态</span>
        <span>召回</span>
        <span>耗时</span>
        <span>时间</span>
        <span>操作</span>
      </div>
      <article v-for="log in queryLogs" :key="log.id" class="entity-table__row">
        <div class="entity-main">
          <strong>{{ formatQueryLogUser(log) }}</strong>
          <span>知识库：{{ formatQueryLogKnowledgeBases(log) }}</span>
          <span>
            {{ formatQueryScopeMode(log.query_scope_mode) }} /
            {{ log.resolved_kb_count }} 个知识库 /
            {{ log.rewrite_count }} 条检索 query
          </span>
        </div>
        <div class="entity-cell">
          <StatusBadge
            :label="formatQueryLogStatus(log)"
            :tone="queryLogStatusTone(log)"
          />
          <span v-if="log.degrade_reason || log.error_code">
            {{ formatDiagnosticReasonList(log.degrade_reason ?? log.error_code, "") }}
          </span>
        </div>
        <div class="entity-cell">{{ log.candidate_count }} 候选 / {{ log.citation_count }} 引用</div>
        <div class="entity-cell">{{ formatLatency(log.latency_ms) }}</div>
        <div class="entity-cell">{{ formatAuditTime(log.created_at) }}</div>
        <div class="row-actions row-actions--dense">
          <button
            class="button button--secondary button--small"
            type="button"
            @click="selectQueryLog(log.id)"
            :disabled="diagnosticsBusy.loadingQueryDetail"
          >
            详情
          </button>
        </div>
      </article>
    </div>
    <p v-else-if="canLoadDiagnostics" class="empty-state empty-state--plain">当前尚未读取到查询日志。</p>
    <PaginationBar
      v-if="queryLogPagination.total > 0"
      label="查询日志分页"
      :page="queryLogPagination.page"
      :page-size="queryLogPagination.pageSize"
      :total="queryLogPagination.total"
      :page-size-options="pageSizeOptions"
      :disabled="diagnosticsBusy.loadingQueryLogs"
      @update:page="(page) => changePaginationPage(queryLogPagination, refreshQueryLogs, page)"
      @update:page-size="(pageSize) => changePaginationPageSize(queryLogPagination, refreshQueryLogs, pageSize)"
    />
  </section>
</template>
