<script setup lang="ts">
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import { formatAuditTime, formatShortIdentifier } from "@/utils/date";
import {
  formatLatency,
  formatStatusText,
  formatTokenUsage,
} from "@/utils/display";
import {
  formatDiagnosticReasonList,
  formatModelCallStatus,
  formatModelCallTitle,
} from "@/utils/status";

const props = defineProps<{
  runtime: DiagnosticsRuntime;
}>();

const {
  closeModelCallLogDetailModal,
  modelCallLogDetailModalOpen,
  selectedModelCallLog,
} = props.runtime;
</script>

<template>
  <div
    v-if="modelCallLogDetailModalOpen && selectedModelCallLog"
    class="modal-backdrop"
    role="presentation"
    @click.self="closeModelCallLogDetailModal"
  >
    <section class="modal modal--wide" role="dialog" aria-modal="true" aria-labelledby="model-call-log-detail-modal-title">
      <header class="modal__header">
        <div>
          <p class="eyebrow">查询诊断</p>
          <h3 id="model-call-log-detail-modal-title">模型调用详情</h3>
          <p>{{ formatModelCallTitle(selectedModelCallLog) }}</p>
        </div>
        <button class="button button--secondary button--small" type="button" @click="closeModelCallLogDetailModal">
          关闭
        </button>
      </header>
      <div class="modal__body">
        <dl class="summary summary--compact modal-summary">
          <div class="summary__row">
            <dt>模型</dt>
            <dd>{{ selectedModelCallLog.model_name }}</dd>
          </div>
          <div class="summary__row">
            <dt>类型</dt>
            <dd>{{ formatStatusText(selectedModelCallLog.model_type) }}</dd>
          </div>
          <div class="summary__row">
            <dt>版本</dt>
            <dd>{{ selectedModelCallLog.model_version ?? "-" }}</dd>
          </div>
          <div class="summary__row">
            <dt>调用方</dt>
            <dd>{{ selectedModelCallLog.caller }}</dd>
          </div>
          <div class="summary__row">
            <dt>状态</dt>
            <dd>{{ formatModelCallStatus(selectedModelCallLog) }}</dd>
          </div>
          <div class="summary__row">
            <dt>耗时</dt>
            <dd>{{ formatLatency(selectedModelCallLog.latency_ms) }}</dd>
          </div>
          <div class="summary__row">
            <dt>调用时间</dt>
            <dd>{{ formatAuditTime(selectedModelCallLog.created_at) }}</dd>
          </div>
          <div class="summary__row">
            <dt>配置版本</dt>
            <dd>{{ selectedModelCallLog.config_version === null ? "-" : `v${selectedModelCallLog.config_version}` }}</dd>
          </div>
          <div class="summary__row">
            <dt>错误码</dt>
            <dd>{{ formatDiagnosticReasonList(selectedModelCallLog.error_code, "-") }}</dd>
          </div>
          <div class="summary__row">
            <dt>Token</dt>
            <dd>{{ formatTokenUsage(selectedModelCallLog.token_usage_json) }}</dd>
          </div>
        </dl>

        <section class="modal-pane">
          <h4>技术追踪</h4>
          <dl class="summary summary--compact modal-summary">
            <div class="summary__row">
              <dt>请求编号</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.request_id) }}</dd>
            </div>
            <div class="summary__row">
              <dt>追踪编号</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.trace_id) }}</dd>
            </div>
            <div class="summary__row">
              <dt>模型路由</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.model_route_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>Prompt 摘要</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.prompt_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>输入摘要</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.input_hash) }}</dd>
            </div>
            <div class="summary__row">
              <dt>输出摘要</dt>
              <dd>{{ formatShortIdentifier(selectedModelCallLog.output_hash) }}</dd>
            </div>
          </dl>
        </section>
      </div>
      <footer class="modal__footer">
        <button class="button button--secondary" type="button" @click="closeModelCallLogDetailModal">
          关闭
        </button>
      </footer>
    </section>
  </div>
</template>
