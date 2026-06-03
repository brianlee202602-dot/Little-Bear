<script setup lang="ts">
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import QueryRetrievalDiagnostics from "@/features/diagnostics/QueryRetrievalDiagnostics.vue";
import { formatAuditTime, formatShortIdentifier } from "@/utils/date";
import { formatLatency } from "@/utils/display";
import {
  formatDiagnosticReasonList,
  formatQueryLogKnowledgeBases,
  formatQueryLogStatus,
  formatQueryLogTitle,
  formatQueryLogUser,
} from "@/utils/status";

const props = defineProps<{
  runtime: DiagnosticsRuntime;
}>();

const {
  closeQueryLogDetailModal,
  queryLogDetailModalOpen,
  selectedQueryLog,
} = props.runtime;
</script>

<template>
  <div
    v-if="queryLogDetailModalOpen && selectedQueryLog"
    class="modal-backdrop"
    role="presentation"
    @click.self="closeQueryLogDetailModal"
  >
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="query-log-detail-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">查询诊断</p>
          <h3 id="query-log-detail-modal-title">查询详情</h3>
          <p>{{ formatQueryLogTitle(selectedQueryLog) }}</p>
        </div>
        <button class="button button--secondary button--small" type="button" @click="closeQueryLogDetailModal">
          关闭
        </button>
      </header>
      <div class="modal__body">
        <dl class="summary summary--compact modal-summary">
          <div class="summary__row">
            <dt>查询时间</dt>
            <dd>{{ formatAuditTime(selectedQueryLog.created_at) }}</dd>
          </div>
          <div class="summary__row">
            <dt>查询结果</dt>
            <dd>{{ formatQueryLogStatus(selectedQueryLog) }}</dd>
          </div>
          <div class="summary__row">
            <dt>用户</dt>
            <dd>{{ formatQueryLogUser(selectedQueryLog) }}</dd>
          </div>
          <div class="summary__row">
            <dt>知识库</dt>
            <dd>{{ formatQueryLogKnowledgeBases(selectedQueryLog) }}</dd>
          </div>
          <div class="summary__row">
            <dt>召回结果</dt>
            <dd>{{ selectedQueryLog.candidate_count }} 个候选 / {{ selectedQueryLog.citation_count }} 个引用</dd>
          </div>
          <div class="summary__row">
            <dt>耗时</dt>
            <dd>{{ formatLatency(selectedQueryLog.latency_ms) }}</dd>
          </div>
          <div class="summary__row">
            <dt>降级原因</dt>
            <dd>{{ formatDiagnosticReasonList(selectedQueryLog.degrade_reason) }}</dd>
          </div>
          <div class="summary__row">
            <dt>错误码</dt>
            <dd>{{ formatDiagnosticReasonList(selectedQueryLog.error_code, "-") }}</dd>
          </div>
          <div class="summary__row">
            <dt>配置版本</dt>
            <dd>v{{ selectedQueryLog.config_version }}</dd>
          </div>
          <div class="summary__row">
            <dt>权限版本</dt>
            <dd>{{ selectedQueryLog.permission_version }}</dd>
          </div>
        </dl>

        <section class="modal-pane">
          <h4>技术追踪</h4>
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>请求编号</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.request_id) }}</dd>
            </div>
            <div class="summary__row">
              <dt>追踪编号</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.trace_id) }}</dd>
            </div>
            <div class="summary__row">
              <dt>查询摘要</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.query_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>权限过滤</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.permission_filter_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>索引版本</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.index_version_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>模型路由</dt>
              <dd>{{ formatShortIdentifier(selectedQueryLog.model_route_hash) }}</dd>
            </div>
          </dl>
        </section>

        <QueryRetrievalDiagnostics
          :diagnostics="selectedQueryLog.retrieval_diagnostics"
        />
      </div>
      <footer class="modal__footer">
        <button class="button button--secondary" type="button" @click="closeQueryLogDetailModal">
          关闭
        </button>
      </footer>
    </section>
  </div>
</template>
