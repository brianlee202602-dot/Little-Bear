<script setup lang="ts">
import type { AuditLogListItemData } from "@/api/audit";
import PaginationBar from "@/components/PaginationBar.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { formatAuditTime } from "@/utils/date";
import { formatStatusText, toneClass } from "@/utils/display";
import { changePaginationPage, changePaginationPageSize } from "@/utils/pagination";
import { auditSummaryPreview } from "@/utils/status";

const props = defineProps<{
  auditFeedback: { tone: "success" | "error" | "neutral"; message: string } | null;
  auditLogPagination: { page: number; pageSize: number; total: number };
  auditLogs: AuditLogListItemData[];
  busy: { loading: boolean };
  canReadAudit: boolean;
  pageSizeOptions: number[];
  refreshAuditLogs: () => Promise<void>;
}>();
</script>

<template>
  <section class="config-secondary-grid config-secondary-grid--single">
    <div class="config-versions" aria-label="配置审计">
      <details class="config-audit-details">
        <summary>配置变更日志</summary>
        <p v-if="props.auditFeedback" :class="toneClass(props.auditFeedback.tone)">
          {{ props.auditFeedback.message }}
        </p>
        <div v-if="props.auditLogs.length" class="audit-list">
          <article v-for="log in props.auditLogs" :key="log.id" class="audit-row">
            <header>
              <strong>{{ log.event_name }}</strong>
              <StatusBadge
                :label="formatStatusText(log.result)"
                :tone="log.result === 'success' ? 'success' : 'error'"
              />
            </header>
            <p>{{ formatAuditTime(log.created_at) }}</p>
            <p>{{ auditSummaryPreview(log) }}</p>
            <p v-if="log.error_code" class="audit-row__error">{{ log.error_code }}</p>
          </article>
        </div>
        <p v-else-if="props.canReadAudit" class="empty-state">当前尚未读取到配置变更日志。</p>
        <p v-else class="empty-state">当前账号缺少审计读取权限。</p>
        <PaginationBar
          v-if="props.auditLogPagination.total > 0"
          label="配置变更日志分页"
          :page="props.auditLogPagination.page"
          :page-size="props.auditLogPagination.pageSize"
          :total="props.auditLogPagination.total"
          :page-size-options="props.pageSizeOptions"
          :disabled="props.busy.loading"
          @update:page="(page) => changePaginationPage(props.auditLogPagination, props.refreshAuditLogs, page)"
          @update:page-size="(pageSize) => changePaginationPageSize(props.auditLogPagination, props.refreshAuditLogs, pageSize)"
        />
      </details>
    </div>
  </section>
</template>
