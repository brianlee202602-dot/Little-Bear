<script setup lang="ts">
import IndexOpsPage from "@/features/diagnostics/IndexOpsPage.vue";
import ModelCallDetailModal from "@/features/diagnostics/ModelCallDetailModal.vue";
import ModelCallLogPage from "@/features/diagnostics/ModelCallLogPage.vue";
import QueryLogDetailModal from "@/features/diagnostics/QueryLogDetailModal.vue";
import QueryLogPage from "@/features/diagnostics/QueryLogPage.vue";
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import { toneClass } from "@/utils/display";

const props = defineProps<{
  pageSizeOptions: number[];
  runtime: DiagnosticsRuntime;
}>();

const {
  canLoadDiagnostics,
  canLoadIndexOps,
  diagnosticsBusy,
  diagnosticsFeedback,
  refreshDiagnosticsState,
} = props.runtime;
</script>

<template>
  <section class="panel panel--wide">
    <header class="panel__header">
      <div>
        <h3>诊断与索引运维</h3>
        <p :class="toneClass(canLoadDiagnostics || canLoadIndexOps ? 'success' : 'warning')">
          {{
            canLoadDiagnostics && canLoadIndexOps
              ? "可读取查询日志、模型调用日志与索引健康"
              : canLoadDiagnostics
                ? "可读取查询日志与模型调用日志，缺少 document:index"
                : canLoadIndexOps
                  ? "可读取索引健康，缺少 audit:read"
                  : "缺少 audit:read 和 document:index"
          }}
        </p>
      </div>
      <div class="panel__actions">
        <button
          class="button button--secondary"
          type="button"
          @click="refreshDiagnosticsState"
          :disabled="(!canLoadDiagnostics && !canLoadIndexOps) || diagnosticsBusy.loadingQueryLogs || diagnosticsBusy.loadingModelCallLogs || diagnosticsBusy.loadingIndexHealth"
        >
          {{ diagnosticsBusy.loadingQueryLogs || diagnosticsBusy.loadingModelCallLogs || diagnosticsBusy.loadingIndexHealth ? "刷新中" : "刷新诊断" }}
        </button>
      </div>
    </header>

    <div class="admin-list-panel">
      <div v-if="diagnosticsFeedback" :class="['feedback feedback--wide', `feedback--${diagnosticsFeedback.tone}`]">
        {{ diagnosticsFeedback.message }}
      </div>

      <IndexOpsPage
        :runtime="runtime"
        :page-size-options="pageSizeOptions"
      />
      <QueryLogPage
        :runtime="runtime"
        :page-size-options="pageSizeOptions"
      />
      <ModelCallLogPage
        :runtime="runtime"
        :page-size-options="pageSizeOptions"
      />
    </div>
  </section>

  <QueryLogDetailModal :runtime="runtime" />
  <ModelCallDetailModal :runtime="runtime" />
</template>
