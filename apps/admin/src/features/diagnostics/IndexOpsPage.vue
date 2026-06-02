<script setup lang="ts">
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import SnapshotPanel from "@/features/diagnostics/SnapshotPanel.vue";
import type { DiagnosticsRuntime } from "@/features/diagnostics/useDiagnostics";
import { formatBoolean, formatStatusText } from "@/utils/display";
import { formatIssueList, indexHealthTone } from "@/utils/status";
import {
  changePaginationPage,
  changePaginationPageSize,
} from "@/utils/pagination";

const props = defineProps<{
  pageSizeOptions: number[];
  runtime: DiagnosticsRuntime;
}>();

const { pageSizeOptions } = props;
const {
  canLoadIndexOps,
  diagnosticsBusy,
  indexHealth,
  indexHealthPagination,
  indexCollectionOpsForm,
  refreshIndexHealth,
} = props.runtime;
</script>

<template>
  <section class="diagnostics-pane">
    <header class="resource-section__header">
      <div>
        <h4>索引运维</h4>
        <p>对比 PostgreSQL 索引账本与 Qdrant collection 状态，暴露 pending_delete、维度和引用数量异常。</p>
      </div>
      <div class="panel__actions">
        <span>{{ diagnosticsBusy.loadingIndexHealth ? "读取中" : `${indexHealthPagination.total} 个集合` }}</span>
        <button
          class="button button--secondary button--small"
          type="button"
          @click="refreshIndexHealth()"
          :disabled="!canLoadIndexOps || diagnosticsBusy.loadingIndexHealth"
        >
          {{ diagnosticsBusy.loadingIndexHealth ? "刷新中" : "刷新索引" }}
        </button>
      </div>
    </header>

    <template v-if="indexHealth.length">
      <div class="index-health-list">
        <article
          v-for="item in indexHealth"
          :key="item.collection_name"
          class="index-health-card"
          :class="{ 'index-health-card--selected': item.collection_name === indexCollectionOpsForm.selectedCollectionName }"
        >
          <header class="index-health-card__header">
            <div>
              <strong>{{ item.collection_name }}</strong>
              <span>期望维度 {{ item.expected_dimension ?? "-" }}</span>
            </div>
            <StatusBadge
              :label="
                item.qdrant_reachable
                  ? `${formatStatusText(item.qdrant_status ?? 'unknown')} / ${item.qdrant_vector_size ?? '-'}d`
                  : formatStatusText('unreachable')
              "
              :tone="indexHealthTone(item)"
            />
          </header>
          <dl class="index-health-metrics">
            <div class="index-health-metric">
              <dt>Qdrant</dt>
              <dd>points {{ item.qdrant_points_count ?? "-" }}</dd>
              <dd>exists {{ item.qdrant_exists === null ? "-" : formatBoolean(item.qdrant_exists) }}</dd>
            </div>
            <div class="index-health-metric">
              <dt>索引版本</dt>
              <dd>active {{ item.active_index_version_count }}</dd>
              <dd>pending {{ item.pending_delete_index_version_count }} / failed {{ item.failed_index_version_count }}</dd>
            </div>
            <div class="index-health-metric">
              <dt>引用</dt>
              <dd>active {{ item.active_ref_count }} / draft {{ item.draft_ref_count }}</dd>
              <dd>deleted {{ item.deleted_ref_count }} / pending {{ item.pending_delete_ref_count }}</dd>
            </div>
            <div class="index-health-metric">
              <dt>问题</dt>
              <dd>{{ formatIssueList(item.issues) }}</dd>
            </div>
          </dl>
        </article>
      </div>
      <PaginationBar
        v-if="indexHealthPagination.total > 0"
        label="索引集合分页"
        :page="indexHealthPagination.page"
        :page-size="indexHealthPagination.pageSize"
        :total="indexHealthPagination.total"
        :page-size-options="pageSizeOptions"
        :disabled="diagnosticsBusy.loadingIndexHealth"
        @update:page="(page) => changePaginationPage(indexHealthPagination, () => refreshIndexHealth(), page)"
        @update:page-size="(pageSize) => changePaginationPageSize(indexHealthPagination, () => refreshIndexHealth(), pageSize)"
      />

      <SnapshotPanel
        :runtime="runtime"
        :page-size-options="pageSizeOptions"
      />
    </template>
    <p v-else-if="canLoadIndexOps" class="empty-state empty-state--plain">当前尚未读取到索引 collection。</p>
    <p v-else class="empty-state empty-state--plain">当前账号缺少 document:index，无法查看索引运维诊断。</p>
  </section>
</template>
